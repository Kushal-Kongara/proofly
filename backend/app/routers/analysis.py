"""Document analysis endpoints: one batch Featherless extraction over all
completed demo-container documents, followed by a deterministic timeline.

In-process storage only. `_latest_analysis` is a module-level variable — it
is lost on restart and is not shared across multiple worker processes. That
is an accepted, documented limitation for this one-day prototype; a real
deployment needs a database (or at least a shared cache) here instead. See
docs/ARCHITECTURE.md.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.analysis import AnalysisResult, TimelineAnalysisEvent
from app.services.featherless_service import (
    FeatherlessConfigurationError,
    FeatherlessInputTooLargeError,
    FeatherlessService,
    FeatherlessUpstreamError,
    FeatherlessValidationError,
    get_featherless_service,
)
from app.services.supermemory_service import (
    SupermemoryConfigurationError,
    SupermemoryService,
    SupermemoryUpstreamError,
    get_supermemory_service,
)
from app.services.timeline import build_timeline

router = APIRouter(prefix="/api", tags=["analysis"])

_latest_analysis: AnalysisResult | None = None
_store_lock = asyncio.Lock()


def _handle_analysis_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (SupermemoryConfigurationError, FeatherlessConfigurationError)):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Document analysis is not configured")
    if isinstance(exc, FeatherlessInputTooLargeError):
        return HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Too much document content to analyze at once")
    if isinstance(exc, FeatherlessValidationError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Document analysis returned an invalid result")
    if isinstance(exc, (SupermemoryUpstreamError, FeatherlessUpstreamError)):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Document analysis upstream error")
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unexpected document analysis error")


@router.post("/analysis/run", response_model=AnalysisResult, status_code=status.HTTP_201_CREATED)
async def run_analysis(
    supermemory_service: SupermemoryService = Depends(get_supermemory_service),
    featherless_service: FeatherlessService = Depends(get_featherless_service),
) -> AnalysisResult:
    global _latest_analysis

    try:
        documents = await supermemory_service.list_completed_documents_with_content()
    except (SupermemoryConfigurationError, SupermemoryUpstreamError) as exc:
        raise _handle_analysis_error(exc) from exc

    if not documents:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No processed documents are available for analysis.",
        )

    as_of = _today()

    try:
        llm_output = await featherless_service.analyze_documents(documents)
    except (
        FeatherlessConfigurationError,
        FeatherlessInputTooLargeError,
        FeatherlessValidationError,
        FeatherlessUpstreamError,
    ) as exc:
        raise _handle_analysis_error(exc) from exc

    timeline: list[TimelineAnalysisEvent] = build_timeline(llm_output, as_of)
    result = AnalysisResult(**llm_output.model_dump(), as_of_date=as_of, timeline=timeline)

    async with _store_lock:
        _latest_analysis = result

    return result


@router.get("/analysis/latest", response_model=AnalysisResult)
async def get_latest_analysis() -> AnalysisResult:
    if _latest_analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No analysis has run yet")
    return _latest_analysis


@router.get("/timeline", response_model=list[TimelineAnalysisEvent])
async def get_timeline() -> list[TimelineAnalysisEvent]:
    if _latest_analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No analysis has run yet")
    return _latest_analysis.timeline


def _today() -> date:
    return datetime.now(tz=timezone.utc).date()
