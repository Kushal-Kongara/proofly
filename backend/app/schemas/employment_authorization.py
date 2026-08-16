from datetime import date

from pydantic import BaseModel, Field

from app.schemas.common import EmploymentAuthorizationType, VerificationStatus
from app.schemas.source_citation import SourceCitation


class EmploymentAuthorization(BaseModel):
    """A period of work authorization (e.g. post-completion OPT, STEM OPT
    extension) held under an underlying ImmigrationStatus classification.

    Unlike ImmigrationStatus, an EAD always carries a fixed, printed
    expiration date — end_date is required here, never a D/S-style open end.
    """

    id: str
    user_id: str
    authorization_type: EmploymentAuthorizationType
    start_date: date
    end_date: date
    is_current: bool = False
    source: SourceCitation | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
