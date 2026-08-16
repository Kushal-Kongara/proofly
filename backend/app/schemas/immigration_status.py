from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ImmigrationStatusType, VerificationStatus
from app.schemas.source_citation import SourceCitation


class ImmigrationStatus(BaseModel):
    """The user's underlying immigration classification (e.g. F-1), not a period
    of employment authorization (see EmploymentAuthorization) and not a visa
    stamp (see VisaStamp).

    Most nonimmigrant students are admitted "D/S" (duration of status) on
    their I-94 — there is no fixed date on which F-1 status itself expires,
    and this schema must not be made to imply one. When `duration_of_status`
    is True, `end_date` is always None: do not invent a fixed expiration
    date, and do not compute a numerical countdown against it.
    """

    id: str
    user_id: str
    status_type: ImmigrationStatusType
    start_date: date
    duration_of_status: bool = Field(
        True,
        description="True when the I-94 admit-until value is 'D/S'. When True, end_date must be None.",
    )
    end_date: date | None = Field(
        None,
        description="Only meaningful when duration_of_status is False. May still be None if a fixed "
        "admission end date exists but is not yet known — never invent one.",
    )
    is_current: bool = False
    source: SourceCitation | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED

    @model_validator(mode="after")
    def _duration_of_status_has_no_end_date(self) -> "ImmigrationStatus":
        if self.duration_of_status and self.end_date is not None:
            raise ValueError("end_date must be None when duration_of_status is True (I-94 'D/S')")
        return self
