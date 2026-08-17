"""Official immigration updates endpoint (Phase 6): searches current
official government sources via Tavily and returns validated links/
snippets. Awareness only — a result is never claimed to change the user's
case, and nothing here is personalized legal advice. See
`app/services/tavily_service.py` and `docs/ARCHITECTURE.md`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.data.immigration_updates import OFFICIAL_DOMAINS, UPDATES_DISCLAIMER
from app.schemas.immigration_update import UpdateCategory, UpdateTimeRange, UpdatesResponse
from app.services.tavily_service import (
    TavilyConfigurationError,
    TavilyService,
    TavilyUpstreamError,
    get_tavily_service,
)

router = APIRouter(prefix="/api", tags=["updates"])


def _handle_updates_error(exc: Exception) -> HTTPException:
    if isinstance(exc, TavilyConfigurationError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Official updates search is not configured")
    if isinstance(exc, TavilyUpstreamError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Official updates upstream error")
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unexpected official updates error")


@router.get("/updates", response_model=UpdatesResponse)
async def get_updates(
    category: UpdateCategory,
    time_range: UpdateTimeRange = UpdateTimeRange.YEAR,
    tavily_service: TavilyService = Depends(get_tavily_service),
) -> UpdatesResponse:
    try:
        results, cache_hit, retrieved_at = await tavily_service.search_updates(category=category, time_range=time_range)
    except (TavilyConfigurationError, TavilyUpstreamError) as exc:
        raise _handle_updates_error(exc) from exc

    return UpdatesResponse(
        category=category,
        time_range=time_range,
        results=results,
        official_domains=OFFICIAL_DOMAINS,
        retrieved_at=retrieved_at,
        cache_hit=cache_hit,
        disclaimer=UPDATES_DISCLAIMER,
    )
