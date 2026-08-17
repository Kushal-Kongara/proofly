"""TavilyService unit tests (Phase 6). `tavily.AsyncTavilyClient` is always
monkeypatched with an in-memory fake, so these tests never touch the
network or consume a Tavily credit.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.config import Settings
from app.data.immigration_updates import CATEGORY_QUERIES, OFFICIAL_DOMAINS
from app.schemas.immigration_update import MAX_SNIPPET_LENGTH, UpdateCategory, UpdateTimeRange
from app.services import tavily_service as ts_module
from app.services.tavily_service import (
    TavilyConfigurationError,
    TavilyService,
    TavilyUpstreamError,
    _canonicalize_url,
    _matching_official_domain,
    _normalize_results,
    _parse_published_date,
    _truncate_snippet,
)


def _settings(**overrides) -> Settings:
    base = {
        "tavily_api_key": "tvly_test_key",
        "tavily_request_timeout_seconds": 5.0,
        "tavily_cache_ttl_seconds": 900,
    }
    base.update(overrides)
    return Settings(**base)


def _raw_result(**overrides) -> dict:
    base = {
        "title": "USCIS Policy Update",
        "url": "https://www.uscis.gov/newsroom/some-update",
        "content": "Some official policy update content.",
        "score": 0.87,
        "published_date": "2026-07-01",
    }
    base.update(overrides)
    return base


class FakeAsyncTavilyClient:
    """A fresh client instance is constructed per `TavilyService._client()`
    call (mirroring `FeatherlessService._client()`), so call tracking lives
    on the class itself (`total_calls`), not on a single instance.
    """

    last_instance: "FakeAsyncTavilyClient | None" = None
    total_calls: list[dict] = []

    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key
        type(self).last_instance = self

    async def search(self, **kwargs) -> dict:
        type(self).total_calls.append(kwargs)
        queue = type(self).queue
        if isinstance(queue, Exception):
            raise queue
        return queue


def make_fake_client_class(response_or_exception):
    class _Client(FakeAsyncTavilyClient):
        queue = response_or_exception
        total_calls: list[dict] = []

    return _Client


@pytest.fixture(autouse=True)
def reset_cache():
    ts_module._CACHE.clear()
    yield
    ts_module._CACHE.clear()


# --- URL canonicalization / domain validation -------------------------------


def test_http_url_is_rejected():
    assert _canonicalize_url("http://www.uscis.gov/page") is None


def test_https_url_is_accepted_and_fragment_stripped():
    canonical = _canonicalize_url("https://www.uscis.gov/page#section-2")
    assert canonical == "https://www.uscis.gov/page"


def test_tracking_params_are_stripped_but_other_params_kept():
    canonical = _canonicalize_url("https://www.uscis.gov/page?utm_source=x&id=42&gclid=abc")
    assert canonical == "https://www.uscis.gov/page?id=42"


def test_deceptive_lookalike_domains_are_rejected():
    assert _matching_official_domain("fakeuscis.gov") is None
    assert _matching_official_domain("uscis.gov.example.com") is None


def test_exact_and_subdomain_official_domains_accepted():
    assert _matching_official_domain("uscis.gov") == "uscis.gov"
    assert _matching_official_domain("www.uscis.gov") == "uscis.gov"
    assert _matching_official_domain("studyinthestates.dhs.gov") in {"dhs.gov", "studyinthestates.dhs.gov"}


# --- published_date -----------------------------------------------------


def test_missing_published_date_remains_null():
    assert _parse_published_date(None) is None
    assert _parse_published_date("") is None


def test_valid_published_date_is_parsed():
    assert _parse_published_date("2026-07-01") == date(2026, 7, 1)


def test_unparseable_published_date_remains_null_never_invented():
    assert _parse_published_date("not a date") is None


# --- snippet truncation ---------------------------------------------------


def test_short_snippet_is_kept_verbatim():
    assert _truncate_snippet("short content") == "short content"


def test_long_snippet_is_truncated_with_ellipsis():
    long_content = "word " * 200
    truncated = _truncate_snippet(long_content)
    assert len(truncated) <= MAX_SNIPPET_LENGTH + 1
    assert truncated.endswith("…")


# --- result normalization / validation ------------------------------------


def test_result_with_empty_title_is_rejected():
    results = _normalize_results(
        [_raw_result(title="")], category=UpdateCategory.GENERAL, retrieved_at=datetime.now(timezone.utc)
    )
    assert results == []


def test_result_with_http_url_is_rejected():
    results = _normalize_results(
        [_raw_result(url="http://www.uscis.gov/page")],
        category=UpdateCategory.GENERAL,
        retrieved_at=datetime.now(timezone.utc),
    )
    assert results == []


def test_result_with_deceptive_domain_is_rejected():
    results = _normalize_results(
        [_raw_result(url="https://fakeuscis.gov/page")],
        category=UpdateCategory.GENERAL,
        retrieved_at=datetime.now(timezone.utc),
    )
    assert results == []


def test_url_deduplication_after_tracking_param_stripping():
    raw = [
        _raw_result(url="https://www.uscis.gov/page?utm_source=a"),
        _raw_result(url="https://www.uscis.gov/page?utm_source=b"),
    ]
    results = _normalize_results(raw, category=UpdateCategory.GENERAL, retrieved_at=datetime.now(timezone.utc))
    assert len(results) == 1


def test_valid_official_subdomain_result_is_normalized():
    results = _normalize_results(
        [_raw_result(url="https://studyinthestates.dhs.gov/page")],
        category=UpdateCategory.F1_OPT,
        retrieved_at=datetime.now(timezone.utc),
    )
    assert len(results) == 1
    assert results[0].source_type == "official_government"
    assert results[0].category == UpdateCategory.F1_OPT


# --- deterministic deduplication (canonical URL + domain/title/snippet) --


def test_identical_urls_are_deduplicated():
    raw = [_raw_result(url="https://www.uscis.gov/page"), _raw_result(url="https://www.uscis.gov/page")]
    results = _normalize_results(raw, category=UpdateCategory.GENERAL, retrieved_at=datetime.now(timezone.utc))
    assert len(results) == 1


def test_url_fragment_and_trailing_slash_variants_are_deduplicated():
    raw = [
        _raw_result(url="https://www.uscis.gov/page/", score=0.9),
        _raw_result(url="https://www.uscis.gov/page#section-2", score=0.5),
        _raw_result(url="https://www.uscis.gov/page", score=0.4),
    ]
    results = _normalize_results(raw, category=UpdateCategory.GENERAL, retrieved_at=datetime.now(timezone.utc))
    assert len(results) == 1
    # First occurrence wins — the trailing-slash variant's own score, not a later duplicate's.
    assert results[0].relevance_score == 0.9


def test_identical_content_different_urls_is_deduplicated():
    raw = [
        _raw_result(
            url="https://www.uscis.gov/page-a",
            title="STEM OPT Policy Update",
            content="Identical announcement text.",
        ),
        _raw_result(
            url="https://www.uscis.gov/page-b",
            title="STEM OPT Policy Update",
            content="Identical announcement text.",
        ),
    ]
    results = _normalize_results(raw, category=UpdateCategory.GENERAL, retrieved_at=datetime.now(timezone.utc))
    assert len(results) == 1
    assert results[0].url == "https://www.uscis.gov/page-a"


def test_same_title_different_snippet_is_not_deduplicated():
    raw = [
        _raw_result(url="https://www.uscis.gov/page-a", title="Policy Manual", content="Chapter 1 content."),
        _raw_result(url="https://www.uscis.gov/page-b", title="Policy Manual", content="Chapter 2 content."),
    ]
    results = _normalize_results(raw, category=UpdateCategory.GENERAL, retrieved_at=datetime.now(timezone.utc))
    assert len(results) == 2


def test_dedup_preserves_stable_tavily_relevance_order():
    raw = [
        _raw_result(url="https://www.uscis.gov/first", title="First", content="First content."),
        _raw_result(url="https://www.uscis.gov/first", title="First (dup)", content="Different but url dup."),
        _raw_result(url="https://www.uscis.gov/second", title="Second", content="Second content."),
    ]
    results = _normalize_results(raw, category=UpdateCategory.GENERAL, retrieved_at=datetime.now(timezone.utc))
    assert [r.url for r in results] == ["https://www.uscis.gov/first", "https://www.uscis.gov/second"]


def test_results_are_capped_at_max_results_after_dedup():
    raw = [_raw_result(url=f"https://www.uscis.gov/page-{i}", title=f"Title {i}", content=f"Content {i}") for i in range(8)]
    results = _normalize_results(raw, category=UpdateCategory.GENERAL, retrieved_at=datetime.now(timezone.utc))
    assert len(results) == ts_module.MAX_RESULTS
    assert [r.url for r in results] == [f"https://www.uscis.gov/page-{i}" for i in range(ts_module.MAX_RESULTS)]


# --- TavilyService: configuration / request shape / errors / caching ------


@pytest.mark.anyio
async def test_missing_api_key_raises_configuration_error():
    service = TavilyService(settings=_settings(tavily_api_key=None))
    with pytest.raises(TavilyConfigurationError):
        await service.search_updates(category=UpdateCategory.GENERAL, time_range=UpdateTimeRange.YEAR)


@pytest.mark.anyio
async def test_search_uses_fixed_category_query_and_correct_request_parameters(monkeypatch: pytest.MonkeyPatch):
    fake_cls = make_fake_client_class({"results": [_raw_result()]})
    monkeypatch.setattr(ts_module, "AsyncTavilyClient", fake_cls)

    service = TavilyService(settings=_settings())
    await service.search_updates(category=UpdateCategory.F1_OPT, time_range=UpdateTimeRange.MONTH)

    call = fake_cls.total_calls[0]
    assert call["query"] == CATEGORY_QUERIES[UpdateCategory.F1_OPT]
    assert call["search_depth"] == "basic"
    assert call["topic"] == "general"
    assert call["time_range"] == "month"
    assert call["max_results"] == 5
    assert call["include_domains"] == OFFICIAL_DOMAINS
    assert call["include_answer"] is False
    assert call["include_raw_content"] is False
    assert call["include_images"] is False
    assert call["timeout"] == 5.0


@pytest.mark.anyio
async def test_upstream_failure_is_wrapped_and_never_leaks_details(monkeypatch: pytest.MonkeyPatch):
    fake_cls = make_fake_client_class(RuntimeError("some internal Tavily detail, api_key=tvly_secret"))
    monkeypatch.setattr(ts_module, "AsyncTavilyClient", fake_cls)

    service = TavilyService(settings=_settings())
    with pytest.raises(TavilyUpstreamError) as exc_info:
        await service.search_updates(category=UpdateCategory.GENERAL, time_range=UpdateTimeRange.YEAR)

    assert "tvly_secret" not in str(exc_info.value)


@pytest.mark.anyio
async def test_cache_prevents_a_second_tavily_call(monkeypatch: pytest.MonkeyPatch):
    fake_cls = make_fake_client_class({"results": [_raw_result()]})
    monkeypatch.setattr(ts_module, "AsyncTavilyClient", fake_cls)

    service = TavilyService(settings=_settings())
    _, first_cache_hit, _ = await service.search_updates(category=UpdateCategory.GENERAL, time_range=UpdateTimeRange.YEAR)
    _, second_cache_hit, _ = await service.search_updates(category=UpdateCategory.GENERAL, time_range=UpdateTimeRange.YEAR)

    assert first_cache_hit is False
    assert second_cache_hit is True
    assert len(fake_cls.total_calls) == 1


@pytest.mark.anyio
async def test_cached_response_remains_deduplicated(monkeypatch: pytest.MonkeyPatch):
    raw_with_duplicates = {
        "results": [
            _raw_result(url="https://www.uscis.gov/page"),
            _raw_result(url="https://www.uscis.gov/page/"),  # trailing-slash variant of the same URL
            _raw_result(url="https://www.uscis.gov/other", title="A Different Update", content="Unrelated content."),
        ]
    }
    fake_cls = make_fake_client_class(raw_with_duplicates)
    monkeypatch.setattr(ts_module, "AsyncTavilyClient", fake_cls)

    service = TavilyService(settings=_settings())
    first_results, first_cache_hit, _ = await service.search_updates(
        category=UpdateCategory.GENERAL, time_range=UpdateTimeRange.YEAR
    )
    second_results, second_cache_hit, _ = await service.search_updates(
        category=UpdateCategory.GENERAL, time_range=UpdateTimeRange.YEAR
    )

    assert first_cache_hit is False
    assert len(first_results) == 2
    assert second_cache_hit is True
    assert len(second_results) == 2
    assert [r.url for r in second_results] == [r.url for r in first_results]
    assert len(fake_cls.total_calls) == 1


@pytest.mark.anyio
async def test_cache_key_distinguishes_category_and_time_range(monkeypatch: pytest.MonkeyPatch):
    fake_cls = make_fake_client_class({"results": [_raw_result()]})
    monkeypatch.setattr(ts_module, "AsyncTavilyClient", fake_cls)

    service = TavilyService(settings=_settings())
    await service.search_updates(category=UpdateCategory.GENERAL, time_range=UpdateTimeRange.YEAR)
    await service.search_updates(category=UpdateCategory.F1_OPT, time_range=UpdateTimeRange.YEAR)
    await service.search_updates(category=UpdateCategory.GENERAL, time_range=UpdateTimeRange.MONTH)

    assert len(fake_cls.total_calls) == 3


@pytest.mark.anyio
async def test_expired_cache_entry_triggers_a_new_call(monkeypatch: pytest.MonkeyPatch):
    fake_cls = make_fake_client_class({"results": [_raw_result()]})
    monkeypatch.setattr(ts_module, "AsyncTavilyClient", fake_cls)

    service = TavilyService(settings=_settings(tavily_cache_ttl_seconds=900))
    await service.search_updates(category=UpdateCategory.GENERAL, time_range=UpdateTimeRange.YEAR)

    # Force the cached entry into the past instead of waiting 15 minutes.
    cache_key = (UpdateCategory.GENERAL, UpdateTimeRange.YEAR)
    entry = ts_module._CACHE[cache_key]
    ts_module._CACHE[cache_key] = ts_module._CacheEntry(
        results=entry.results,
        retrieved_at=entry.retrieved_at,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )

    _, cache_hit, _ = await service.search_updates(category=UpdateCategory.GENERAL, time_range=UpdateTimeRange.YEAR)

    assert cache_hit is False
    assert len(fake_cls.total_calls) == 2
