"""O-1A evidence-readiness planner (Phase 4) data contracts.

Two layers, kept deliberately separate:

- `O1EvidenceItemDraft` / `O1CriterionNoteDraft` / `O1LLMAnalysisOutput` are
  exactly the JSON shape Featherless must return — raw, document-grounded
  facts only. The model never outputs a criterion `status`, a coverage
  count, or a legal conclusion; it only reports what a document says, who
  it's about, and (via `evidence_role`/`limitations`) how strong that
  evidence looks on its face.
- `O1CriterionDefinition`, `O1EvidenceItem`, `O1CriterionAssessment`,
  `O1Gap`, `O1ActionItem`, and `O1Assessment` are what
  `app/services/o1_assessment.py` deterministically builds in Python from
  validated `O1LLMAnalysisOutput` plus the static criteria in
  `app/data/o1_criteria.py`. Every status, count, and coverage label is
  computed in code — never asked of, or trusted from, the model.

Status values are intentionally never `eligible`/`ineligible`/`approved`/
`denied`/`criterion_satisfied` — Proofly organizes document evidence and
identifies gaps; it never determines legal sufficiency. See
`docs/PRODUCT_SPEC.md` and `docs/ARCHITECTURE.md`.
"""

from __future__ import annotations

from datetime import date as date_
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, model_validator

from app.schemas.common import O1CriterionCode

NeedsUserReview = Literal["needs_user_review"]


class O1EvidenceRole(str, Enum):
    """How directly a piece of evidence speaks to a criterion."""

    DIRECT_DOCUMENT = "direct_document"
    SUPPORTING_DOCUMENT = "supporting_document"
    SELF_REPORTED = "self_reported"


class O1CriterionStatus(str, Enum):
    """Document-coverage status only — never a legal-sufficiency determination."""

    DOCUMENTED_SUPPORT_FOUND = "documented_support_found"
    PARTIAL_SUPPORT_FOUND = "partial_support_found"
    NO_SUPPORT_FOUND = "no_support_found"
    NEEDS_EXPERT_REVIEW = "needs_expert_review"


class O1DocumentationCoverage(str, Enum):
    LIMITED = "limited"
    DEVELOPING = "developing"
    BROAD = "broad"


class O1ActionType(str, Enum):
    """Evidence-gathering actions only — never a filing or legal-strategy instruction."""

    COLLECT_DOCUMENT = "collect_document"
    REQUEST_CONFIRMATION = "request_confirmation"
    COLLECT_METRICS = "collect_metrics"
    OBTAIN_INDEPENDENT_EVIDENCE = "obtain_independent_evidence"
    VERIFY_FACT = "verify_fact"
    ATTORNEY_REVIEW = "attorney_review"


class O1ActionPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# --- Static, version-controlled criteria data (app/data/o1_criteria.py) ---


class O1CriterionDefinition(BaseModel):
    """One of the eight regulatory O-1A criteria, 8 CFR 214.2(o)(3)(iii).

    Static application data only — this is never produced by the model.
    `app/services/o1_assessment.py` always sources this from
    `app/data/o1_criteria.O1_CRITERIA`, never from Featherless output, so
    the definition text can never be replaced or reworded by a model call.
    """

    code: O1CriterionCode
    name: str
    regulatory_description: str
    official_sources: list[str] = []


class O1InformationalCategory(BaseModel):
    """A related informational concept that is not one of the eight
    criteria (one-time major achievement; comparable evidence).
    """

    name: str
    description: str
    official_sources: list[str] = []


class O1CriteriaResponse(BaseModel):
    """`GET /api/o1/criteria` response — the full static reference set."""

    criteria: list[O1CriterionDefinition]
    one_time_achievement: O1InformationalCategory
    comparable_evidence: O1InformationalCategory
    official_sources: list[str]
    last_reviewed: date_


# --- Raw Featherless extraction output (validated, never trusted for status/counts) ---


class O1EvidenceItemDraft(BaseModel):
    """One evidence fact as reported by Featherless. Carries no status,
    count, or legal conclusion — only what the document says and how
    directly it speaks to the criterion.
    """

    title: str
    factual_summary: str
    criterion_id: O1CriterionCode
    source_document_id: str
    source_filename: str
    page_number: int | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    verification_status: NeedsUserReview = "needs_user_review"
    evidence_role: O1EvidenceRole
    limitations: list[str] = []
    date: date_ | None = None
    is_one_time_major_achievement: bool = False
    is_comparable_evidence: bool = False
    flag_for_expert_review: bool = False


class O1CriterionNoteDraft(BaseModel):
    """Optional short factual notes the model may attach to a criterion it
    found evidence for. Never a satisfaction/approval statement.
    """

    criterion_id: O1CriterionCode
    why_documents_may_be_relevant: str
    what_remains_unproven: str
    suggested_evidence_to_collect: list[str] = []


def _cited_document_ids(data: "O1LLMAnalysisOutput") -> set[str]:
    return {item.source_document_id for item in data.evidence_items}


class O1LLMAnalysisOutput(BaseModel):
    """Exactly the JSON shape Featherless must return for the O-1A planner.

    Validated with `model_validate(data, context={"valid_document_ids": {...}})`
    so a single Pydantic pass also rejects citations referencing documents
    that were never supplied — no citation may point outside the analyzed
    set (same pattern as `LLMAnalysisOutput` in `app/schemas/analysis.py`).
    """

    evidence_items: list[O1EvidenceItemDraft] = []
    criterion_notes: list[O1CriterionNoteDraft] = []

    @model_validator(mode="after")
    def _citations_reference_only_supplied_documents(self, info: ValidationInfo) -> "O1LLMAnalysisOutput":
        context = info.context or {}
        valid_ids = context.get("valid_document_ids")
        if valid_ids is None:
            return self
        unknown = _cited_document_ids(self) - set(valid_ids)
        if unknown:
            raise ValueError(f"citations reference unknown document IDs: {sorted(unknown)}")
        return self


# --- Deterministically-built assessment (app/services/o1_assessment.py) ---


class O1EvidenceItem(BaseModel):
    """A materialized evidence item attached to a criterion assessment.

    `is_future_dated` is computed in Python by comparing `date` against the
    assessment's `as_of_date` — never taken from the model — so a judging
    invitation dated after today can never be silently treated as completed
    judging.
    """

    id: str
    title: str
    factual_summary: str
    criterion_id: O1CriterionCode
    source_document_id: str
    source_filename: str
    page_number: int | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    verification_status: NeedsUserReview = "needs_user_review"
    evidence_role: O1EvidenceRole
    limitations: list[str] = []
    date: date_ | None = None
    is_future_dated: bool = False
    is_one_time_major_achievement: bool = False
    is_comparable_evidence: bool = False


class O1CriterionAssessment(BaseModel):
    """One of the eight criteria plus the evidence found for it. Always
    present for all eight codes, regardless of whether any evidence was
    found — see `build_o1_assessment`.
    """

    definition: O1CriterionDefinition
    status: O1CriterionStatus
    evidence_items: list[O1EvidenceItem] = []
    why_documents_may_be_relevant: str
    what_remains_unproven: str
    suggested_evidence_to_collect: list[str] = []
    requires_attorney_review: Literal[True] = True


class O1Gap(BaseModel):
    criterion_id: O1CriterionCode
    description: str
    priority: O1ActionPriority


class O1ActionItem(BaseModel):
    action_type: O1ActionType
    priority: O1ActionPriority
    related_criterion: O1CriterionCode | None = None
    action: str
    why_it_matters: str
    suggested_supporting_materials: list[str] = []


class O1AssessmentSummary(BaseModel):
    """Document-coverage counts only. `criteria_with_*_count` describe how
    many of the eight criteria have documents mapped to them at each
    status — never a count of criteria "met," "eligible," or "satisfied."
    """

    criteria_with_document_support_count: int
    criteria_with_partial_support_count: int
    criteria_without_support_count: int
    criteria_needing_expert_review_count: int
    one_time_achievement_documented: bool
    comparable_evidence_identified: bool
    documentation_coverage: O1DocumentationCoverage
    highest_priority_gaps: list[O1Gap]
    disclaimer: str
    official_sources: list[str]


class O1Assessment(BaseModel):
    """What `POST /api/o1/assessment/run` and `GET /api/o1/assessment/latest`
    return: all eight criterion assessments, the deterministic coverage
    summary, and a prioritized evidence-gathering action plan.
    """

    criteria: list[O1CriterionAssessment]
    summary: O1AssessmentSummary
    action_plan: list[O1ActionItem]
    as_of_date: date_
