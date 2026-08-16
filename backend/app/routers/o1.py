"""O-1A evidence-readiness planner endpoints (Phase 4): static criteria
reference data, plus one batch Featherless extraction over all completed
demo-container documents, deterministically turned into a full evidence
assessment.

In-process storage only — `_latest_assessment` is a module-level variable,
lost on restart and not shared across worker processes. Same accepted
prototype limitation as `app/routers/analysis.py`; see docs/ARCHITECTURE.md.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.data.o1_criteria import (
    O1_COMPARABLE_EVIDENCE,
    O1_CRITERIA,
    O1_CRITERIA_LAST_REVIEWED,
    O1_ONE_TIME_ACHIEVEMENT,
    O1_OFFICIAL_SOURCES,
)
from app.schemas.o1_assessment import O1Assessment, O1CriteriaResponse
from app.services.featherless_service import (
    FeatherlessConfigurationError,
    FeatherlessInputTooLargeError,
    FeatherlessService,
    FeatherlessUpstreamError,
    FeatherlessValidationError,
    get_featherless_service,
)
from app.services.o1_assessment import build_o1_assessment
from app.services.supermemory_service import (
    SupermemoryConfigurationError,
    SupermemoryService,
    SupermemoryUpstreamError,
    get_supermemory_service,
)

router = APIRouter(prefix="/api/o1", tags=["o1"])

_latest_assessment: O1Assessment | None = None
_store_lock = asyncio.Lock()


def _handle_o1_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (SupermemoryConfigurationError, FeatherlessConfigurationError)):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="O-1A assessment is not configured")
    if isinstance(exc, FeatherlessInputTooLargeError):
        return HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Too much document content to analyze at once")
    if isinstance(exc, FeatherlessValidationError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="O-1A assessment returned an invalid result")
    if isinstance(exc, (SupermemoryUpstreamError, FeatherlessUpstreamError)):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="O-1A assessment upstream error")
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unexpected O-1A assessment error")


@router.get("/criteria", response_model=O1CriteriaResponse)
def get_criteria() -> O1CriteriaResponse:
    return O1CriteriaResponse(
        criteria=O1_CRITERIA,
        one_time_achievement=O1_ONE_TIME_ACHIEVEMENT,
        comparable_evidence=O1_COMPARABLE_EVIDENCE,
        official_sources=O1_OFFICIAL_SOURCES,
        last_reviewed=O1_CRITERIA_LAST_REVIEWED,
    )


@router.post("/assessment/run", response_model=O1Assessment, status_code=status.HTTP_201_CREATED)
async def run_assessment(
    supermemory_service: SupermemoryService = Depends(get_supermemory_service),
    featherless_service: FeatherlessService = Depends(get_featherless_service),
) -> O1Assessment:
    global _latest_assessment

    try:
        documents = await supermemory_service.list_completed_documents_with_content()
    except (SupermemoryConfigurationError, SupermemoryUpstreamError) as exc:
        raise _handle_o1_error(exc) from exc

    if not documents:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No processed documents are available for O-1A assessment.",
        )

    as_of = _today()

    try:
        llm_output = await featherless_service.analyze_o1_evidence(documents)
    except (
        FeatherlessConfigurationError,
        FeatherlessInputTooLargeError,
        FeatherlessValidationError,
        FeatherlessUpstreamError,
    ) as exc:
        raise _handle_o1_error(exc) from exc

    assessment = build_o1_assessment(llm_output, as_of)

    async with _store_lock:
        _latest_assessment = assessment

    return assessment


@router.get("/assessment/latest", response_model=O1Assessment)
async def get_latest_assessment() -> O1Assessment:
    if _latest_assessment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No O-1A assessment has run yet")
    return _latest_assessment


def _today() -> date:
    return datetime.now(tz=timezone.utc).date()
