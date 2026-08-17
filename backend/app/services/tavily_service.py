"""Async facade over Tavily's official search API (tavily-python==0.7.27's
`AsyncTavilyClient`), used for the official immigration updates search
(Phase 6). TAVILY_API_KEY is read only here and never leaves the backend.

Design notes:
- The browser only ever sends a `category` + `time_range` code — never a
  free-text query or a domain list. The actual Tavily query
  (`app/data/immigration_updates.py::CATEGORY_QUERIES`) and the domain
  allowlist (`OFFICIAL_DOMAINS`) are both fixed, server-owned constants.
- Every Tavily result is re-validated here before it's ever turned into an
  `ImmigrationUpdateResult`: HTTPS required, hostname must exactly equal an
  allowed domain or be a true subdomain of one (rejects lookalikes like
  `fakeuscis.gov` or `uscis.gov.example.com`), and title/url must be
  non-empty. `include_domains` scopes the request upstream too, but this
  server-side check is the actual trust boundary — Tavily's own filtering
  is never assumed to be sufficient on its own.
- A publication date is only ever set when Tavily actually supplied one and
  it parses cleanly — never invented, never defaulted to "today."
- Results are deterministically deduplicated after validation/normalization
  (`_normalize_results`) — by canonical URL first, then by
  (domain, normalized title, normalized snippet) — before being capped at
  `MAX_RESULTS` and cached, so the cache never stores a duplicate.
- An in-memory, per-process cache (`_CACHE`) keyed by (category, time_range)
  serves repeat requests within `TAVILY_CACHE_TTL_SECONDS` without spending
  another Tavily credit. Not shared across worker processes and lost on
  restart — see docs/ARCHITECTURE.md.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date as date_
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from tavily import (
    AsyncTavilyClient,
    BadRequestError,
    InvalidAPIKeyError,
    MissingAPIKeyError,
    UsageLimitExceededError,
)
from tavily.errors import ForbiddenError
from tavily.errors import TimeoutError as TavilyTimeoutError

from app.config import Settings
from app.config import settings as default_settings
from app.data.immigration_updates import CATEGORY_QUERIES, OFFICIAL_DOMAINS
from app.schemas.immigration_update import (
    MAX_SNIPPET_LENGTH,
    ImmigrationUpdateResult,
    UpdateCategory,
    UpdateTimeRange,
)

logger = logging.getLogger(__name__)

_TRACKING_PARAM_PREFIXES = ("utm_",)
_TRACKING_PARAM_NAMES = {"gclid", "fbclid", "mc_cid", "mc_eid", "igshid", "ref", "ref_src"}
MAX_RESULTS = 5


class TavilyConfigurationError(RuntimeError):
    """Raised when TAVILY_API_KEY isn't configured, or Tavily rejects it."""


class TavilyUpstreamError(RuntimeError):
    """Raised when the Tavily search call itself fails (network/timeout/5xx/quota)."""


@dataclass
class _CacheEntry:
    results: list[ImmigrationUpdateResult]
    retrieved_at: datetime
    expires_at: datetime


# Module-level, per-process only — see the caching note in the module
# docstring and docs/ARCHITECTURE.md for the accepted limitation.
_CACHE: dict[tuple[UpdateCategory, UpdateTimeRange], _CacheEntry] = {}


def _sanitized_upstream_message(exc: Exception | None) -> str:
    return "Tavily upstream request failed"


def _strip_tracking_params(query: str) -> str:
    pairs = parse_qsl(query, keep_blank_values=True)
    kept = [
        (key, value)
        for key, value in pairs
        if not key.lower().startswith(_TRACKING_PARAM_PREFIXES) and key.lower() not in _TRACKING_PARAM_NAMES
    ]
    return urlencode(kept)


def _canonicalize_url(raw_url: object) -> str | None:
    """HTTPS-only, fragment stripped, known tracking query params stripped.
    Returns `None` for anything that isn't a well-formed `https://` URL with
    a hostname — never guessed or partially repaired.
    """
    if not isinstance(raw_url, str) or not raw_url.strip():
        return None
    try:
        parsed = urlparse(raw_url.strip())
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    path = parsed.path
    if len(path) > 1 and path.endswith("/"):
        # A trailing-slash variant of an otherwise-identical path (e.g.
        # "/page" vs "/page/") is the same resource — normalized so both
        # dedupe to one result. The root path ("/") is left alone.
        path = path.rstrip("/") or "/"
    canonical = parsed._replace(path=path, fragment="", query=_strip_tracking_params(parsed.query))
    return urlunparse(canonical)


def _matching_official_domain(hostname: str) -> str | None:
    """`hostname` must exactly equal an allowed domain, or be a true
    subdomain of one (`www.uscis.gov` matches `uscis.gov`). Rejects
    deceptive lookalikes: `fakeuscis.gov` doesn't equal or end with
    `.uscis.gov`, and `uscis.gov.example.com` ends with `.example.com`, not
    `.uscis.gov`.
    """
    hostname = hostname.lower()
    for domain in OFFICIAL_DOMAINS:
        if hostname == domain or hostname.endswith(f".{domain}"):
            return domain
    return None


def _parse_published_date(raw: object) -> date_ | None:
    """Only ever returns a date Tavily actually supplied and that parses
    cleanly (ISO `YYYY-MM-DD...` or RFC 2822, both of which Tavily has been
    observed to return) — never invents or defaults one.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    value = raw.strip()
    try:
        return date_.fromisoformat(value[:10])
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    return parsed.date()


def _relevance_score(raw: object) -> float | None:
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    return None


def _truncate_snippet(content: object) -> str:
    stripped = content.strip() if isinstance(content, str) else ""
    if len(stripped) <= MAX_SNIPPET_LENGTH:
        return stripped
    truncated = stripped[:MAX_SNIPPET_LENGTH].rsplit(" ", 1)[0]
    return f"{truncated}…"


def _result_id(canonical_url: str) -> str:
    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:16]


def _normalize_text_for_dedup(text: str) -> str:
    """Lowercased, whitespace-collapsed comparison key — never used for
    display, only to decide whether two results are the same content.
    """
    return " ".join(text.lower().split())


def _normalize_result(
    raw: object, *, category: UpdateCategory, retrieved_at: datetime
) -> ImmigrationUpdateResult | None:
    if not isinstance(raw, dict):
        return None

    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        return None

    canonical_url = _canonicalize_url(raw.get("url"))
    if canonical_url is None:
        return None

    hostname = urlparse(canonical_url).hostname or ""
    official_domain = _matching_official_domain(hostname)
    if official_domain is None:
        return None

    return ImmigrationUpdateResult(
        id=_result_id(canonical_url),
        title=title.strip(),
        url=canonical_url,
        official_domain=official_domain,
        snippet=_truncate_snippet(raw.get("content")),
        relevance_score=_relevance_score(raw.get("score")),
        published_date=_parse_published_date(raw.get("published_date")),
        category=category,
        retrieved_at=retrieved_at,
    )


def _normalize_results(
    raw_results: object, *, category: UpdateCategory, retrieved_at: datetime
) -> list[ImmigrationUpdateResult]:
    """Validates, normalizes, and deterministically deduplicates raw Tavily
    results, preserving Tavily's own relevance order (first occurrence
    wins) and capping at `MAX_RESULTS`. Two results are the same result if
    either:
    - their canonicalized URLs match (identical URL, or a fragment/tracking-
      param/trailing-slash variant of the same URL), or
    - they share the same `official_domain` *and* the same normalized title
      *and* the same normalized snippet — title alone is never enough,
      since government sites reuse generic titles (e.g. "Policy Manual")
      across genuinely different pages.
    """
    normalized: list[ImmigrationUpdateResult] = []
    seen_urls: set[str] = set()
    seen_content_keys: set[tuple[str, str, str]] = set()

    for raw in raw_results if isinstance(raw_results, list) else []:
        if len(normalized) >= MAX_RESULTS:
            break

        result = _normalize_result(raw, category=category, retrieved_at=retrieved_at)
        if result is None or result.url in seen_urls:
            continue

        content_key = (
            result.official_domain,
            _normalize_text_for_dedup(result.title),
            _normalize_text_for_dedup(result.snippet),
        )
        if content_key in seen_content_keys:
            continue

        seen_urls.add(result.url)
        seen_content_keys.add(content_key)
        normalized.append(result)

    return normalized


class TavilyService:
    def __init__(self, settings: Settings = default_settings) -> None:
        self._settings = settings

    def _client(self) -> AsyncTavilyClient:
        if not self._settings.tavily_api_key:
            raise TavilyConfigurationError("TAVILY_API_KEY is not configured")
        return AsyncTavilyClient(api_key=self._settings.tavily_api_key)

    async def search_updates(
        self, *, category: UpdateCategory, time_range: UpdateTimeRange
    ) -> tuple[list[ImmigrationUpdateResult], bool, datetime]:
        """Returns `(results, cache_hit, retrieved_at)`. A cache hit never
        calls Tavily — see the module docstring and `_CACHE`.
        """
        cache_key = (category, time_range)
        now = datetime.now(timezone.utc)

        cached = _CACHE.get(cache_key)
        if cached is not None and cached.expires_at > now:
            return cached.results, True, cached.retrieved_at

        client = self._client()
        query = CATEGORY_QUERIES[category]

        try:
            response = await client.search(
                query=query,
                search_depth="basic",
                topic="general",
                time_range=time_range.value,
                max_results=MAX_RESULTS,
                include_domains=OFFICIAL_DOMAINS,
                include_answer=False,
                include_raw_content=False,
                include_images=False,
                timeout=self._settings.tavily_request_timeout_seconds,
            )
        except (InvalidAPIKeyError, MissingAPIKeyError, ForbiddenError) as exc:
            # Never retried — a rejected/missing key is a configuration
            # problem, not a transient one. Mirrors FeatherlessService's
            # AuthenticationError/PermissionDeniedError -> configuration-error mapping.
            raise TavilyConfigurationError("Tavily rejected the configured API key") from exc
        except (BadRequestError, UsageLimitExceededError, TavilyTimeoutError, httpx.HTTPError) as exc:
            raise TavilyUpstreamError(_sanitized_upstream_message(exc)) from exc
        except Exception as exc:  # safety net: never let a raw Tavily/SDK error escape
            raise TavilyUpstreamError(_sanitized_upstream_message(exc)) from exc

        raw_results = response.get("results") if isinstance(response, dict) else None
        results = _normalize_results(raw_results, category=category, retrieved_at=now)

        logger.info(
            "Tavily search: category=%s time_range=%s raw_results=%d accepted_results=%d",
            category.value,
            time_range.value,
            len(raw_results) if isinstance(raw_results, list) else 0,
            len(results),
        )

        _CACHE[cache_key] = _CacheEntry(
            results=results,
            retrieved_at=now,
            expires_at=now + timedelta(seconds=self._settings.tavily_cache_ttl_seconds),
        )
        return results, False, now


def get_tavily_service() -> TavilyService:
    return TavilyService()
