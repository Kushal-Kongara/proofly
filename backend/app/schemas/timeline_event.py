from datetime import date

from pydantic import BaseModel, Field

from app.schemas.common import TimelineEventType, VerificationStatus
from app.schemas.source_citation import SourceCitation


class TimelineEvent(BaseModel):
    """A single dated entry on the user's compliance timeline (deadline, expiration, etc.)."""

    id: str
    user_id: str
    event_type: TimelineEventType
    title: str
    description: str | None = None
    event_date: date
    is_deadline: bool = False
    related_document_ids: list[str] = []
    source: SourceCitation | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
