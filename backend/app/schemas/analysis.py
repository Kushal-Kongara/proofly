"""Structured output contract for Featherless document extraction (Phase 3)
and the deterministic timeline computed from it.

These are deliberately separate from the Phase 1 demo-profile schemas
(`ImmigrationStatus`, `EmploymentAuthorization`, `VisaStamp`, ...) even
though they describe overlapping concepts. The Phase 1 schemas model a
curated, internally-consistent demo profile (e.g. EAD `end_date` is
required). These schemas model *raw, possibly-incomplete facts an LLM
claims to have read out of real documents* — every value must carry a
citation, a confidence score, and start out `needs_user_review`, and dates
are optional because the rule is "never invent a missing value." Reuses
Phase 1's enums (`DocumentType`, `ImmigrationStatusType`,
`EmploymentAuthorizationType`) and `SourceCitation` where the concept is
identical, without modifying those files.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, model_validator

from app.schemas.common import DocumentType, EmploymentAuthorizationType, ImmigrationStatusType
from app.schemas.source_citation import SourceCitation

NeedsUserReview = Literal["needs_user_review"]


class AnalysisFact(BaseModel):
    """One explicit fact read from a document. Never a computed or inferred value."""

    label: str
    value: str
    source_document_id: str
    source_filename: str
    page_number: int | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    verification_status: NeedsUserReview = "needs_user_review"


class AnalyzedDocument(BaseModel):
    document_id: str
    filename: str
    document_type: DocumentType
    facts: list[AnalysisFact] = []


class I94AdmitUntilType(str, Enum):
    DURATION_OF_STATUS = "duration_of_status"
    FIXED_DATE = "fixed_date"
    UNKNOWN = "unknown"


class I94AdmitUntil(BaseModel):
    """The I-94 'admit until' value, kept exactly as printed.

    'D/S' (duration of status) must remain 'duration_of_status' with no
    `date` — it must never be turned into a fabricated expiration date.
    """

    type: I94AdmitUntilType
    raw_value: str = Field(..., description="Verbatim as printed on the document, e.g. 'D/S' or a date")
    admit_until_date: date | None = Field(None, description="Only set when type is 'fixed_date'")

    @model_validator(mode="after")
    def _fixed_date_consistency(self) -> "I94AdmitUntil":
        if self.type == I94AdmitUntilType.FIXED_DATE and self.admit_until_date is None:
            raise ValueError("admit_until.admit_until_date is required when type is 'fixed_date'")
        if self.type != I94AdmitUntilType.FIXED_DATE and self.admit_until_date is not None:
            raise ValueError("admit_until.admit_until_date must be omitted unless type is 'fixed_date'")
        return self


class ReportedImmigrationClassification(BaseModel):
    """The classification as reported by a document (e.g. F-1) — OPT/STEM OPT
    are never valid values here; they are employment authorization, tracked
    separately in `EmploymentAuthorizationRecord`.
    """

    classification: ImmigrationStatusType
    admit_until: I94AdmitUntil
    source_document_id: str
    source_filename: str
    page_number: int | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    verification_status: NeedsUserReview = "needs_user_review"


class AcademicProgramRecord(BaseModel):
    school_name: str | None = None
    program_name: str | None = None
    program_start_date: date | None = None
    program_end_date: date | None = None
    source_document_id: str
    source_filename: str
    page_number: int | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    verification_status: NeedsUserReview = "needs_user_review"


class EmploymentAuthorizationRecord(BaseModel):
    authorization_type: EmploymentAuthorizationType
    start_date: date | None = None
    end_date: date | None = None
    source_document_id: str
    source_filename: str
    page_number: int | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    verification_status: NeedsUserReview = "needs_user_review"


class VisaStampRecord(BaseModel):
    """A visa stamp fact. Never a basis for inferring current legal status on
    its own — see extraction rules in featherless_service.py.
    """

    visa_class: str | None = None
    issue_date: date | None = None
    expiration_date: date | None = None
    source_document_id: str
    source_filename: str
    page_number: int | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    verification_status: NeedsUserReview = "needs_user_review"


class PassportRecord(BaseModel):
    """Only created when a passport expiration date is explicitly present in
    a document — this whole record is optional at the top level.
    """

    expiration_date: date
    source_document_id: str
    source_filename: str
    page_number: int | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    verification_status: NeedsUserReview = "needs_user_review"


class AnalysisConflict(BaseModel):
    description: str
    involved_document_ids: list[str] = []


class MissingInformationItem(BaseModel):
    description: str
    related_document_id: str | None = None


class AnalysisWarning(BaseModel):
    message: str


def _cited_document_ids(data: "LLMAnalysisOutput") -> set[str]:
    ids: set[str] = set()
    for doc in data.analyzed_documents:
        ids.add(doc.document_id)
        for fact in doc.facts:
            ids.add(fact.source_document_id)
    if data.reported_classification:
        ids.add(data.reported_classification.source_document_id)
    if data.academic_program:
        ids.add(data.academic_program.source_document_id)
    for auth in data.employment_authorizations:
        ids.add(auth.source_document_id)
    for visa in data.visa_stamps:
        ids.add(visa.source_document_id)
    if data.passport:
        ids.add(data.passport.source_document_id)
    for conflict in data.conflicts:
        ids.update(conflict.involved_document_ids)
    for item in data.missing_information:
        if item.related_document_id:
            ids.add(item.related_document_id)
    return ids


class LLMAnalysisOutput(BaseModel):
    """Exactly the JSON shape Featherless must return. Validated with
    `model_validate(data, context={"valid_document_ids": {...}})` so a
    single Pydantic validation pass also rejects citations that reference
    documents that were never supplied — no citation may point outside the
    analyzed set.
    """

    analyzed_documents: list[AnalyzedDocument] = []
    reported_classification: ReportedImmigrationClassification | None = None
    academic_program: AcademicProgramRecord | None = None
    employment_authorizations: list[EmploymentAuthorizationRecord] = []
    visa_stamps: list[VisaStampRecord] = []
    passport: PassportRecord | None = None
    conflicts: list[AnalysisConflict] = []
    missing_information: list[MissingInformationItem] = []
    warnings: list[AnalysisWarning] = []

    @model_validator(mode="after")
    def _citations_reference_only_supplied_documents(self, info: ValidationInfo) -> "LLMAnalysisOutput":
        context = info.context or {}
        valid_ids = context.get("valid_document_ids")
        if valid_ids is None:
            return self
        unknown = _cited_document_ids(self) - set(valid_ids)
        if unknown:
            raise ValueError(f"citations reference unknown document IDs: {sorted(unknown)}")
        return self


class TimelineEventCategory(str, Enum):
    WORK_AUTHORIZATION = "work_authorization"
    VISA_VALIDITY = "visa_validity"
    ACADEMIC_PROGRAM = "academic_program"
    PASSPORT = "passport"
    STATUS = "status"
    OTHER = "other"


class TimelineEventDisplayStatus(str, Enum):
    UPCOMING = "upcoming"
    URGENT = "urgent"
    OVERDUE = "overdue"
    HISTORICAL = "historical"
    INFORMATIONAL = "informational"


class TimelineAnalysisEvent(BaseModel):
    """One deterministically-computed timeline entry. Always built in Python
    from validated extracted dates — never asked of the LLM (see
    app/services/timeline.py).

    `status = "overdue"` is reserved for a source explicitly identifying a
    required action or deadline that has been missed; a plain past date
    (an EAD/visa/passport/I-20 date that has simply passed) is
    `"historical"` instead. `affects_authorized_stay=False` is set
    deterministically only for visa-stamp expiration — every other event
    type defaults to `None` (unknown) rather than guessing.
    """

    title: str
    event_date: date | None = None
    category: TimelineEventCategory
    days_remaining: int | None = None
    status: TimelineEventDisplayStatus
    source: SourceCitation
    explanation: str
    affects_authorized_stay: bool | None = Field(None, description="True/False when safely determinable, else unknown (null)")
    requires_user_verification: bool = True


class AnalysisResult(LLMAnalysisOutput):
    """What `/api/analysis/run` and `/api/analysis/latest` return: the
    validated extraction plus the deterministic timeline and the date it
    was computed as of.
    """

    as_of_date: date
    timeline: list[TimelineAnalysisEvent] = []
