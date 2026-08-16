from pydantic import BaseModel, Field

from app.schemas.common import O1CriterionCode, VerificationStatus
from app.schemas.source_citation import SourceCitation


class EvidenceItem(BaseModel):
    """A piece of evidence (usually document-derived) mapped to an O-1A criterion."""

    id: str
    user_id: str
    criterion_code: O1CriterionCode
    title: str
    description: str | None = None
    source: SourceCitation
    confidence: float = Field(..., ge=0.0, le=1.0)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    notes: str | None = None
