from pydantic import BaseModel, Field

from app.schemas.common import VerificationStatus
from app.schemas.source_citation import SourceCitation


class ExtractedFact(BaseModel):
    """A single field pulled from a document by AI (e.g. 'SEVIS ID', 'program end date').

    Every AI-derived fact must be traceable to its source, scored, and
    reviewable by the user before it can be trusted downstream.
    """

    id: str
    document_id: str
    label: str = Field(..., description="Human-readable name of the fact, e.g. 'Program End Date'")
    value: str = Field(..., description="Extracted value, stored as text for display/audit purposes")
    source: SourceCitation
    confidence: float = Field(..., ge=0.0, le=1.0)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
