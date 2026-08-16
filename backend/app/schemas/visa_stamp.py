from datetime import date

from pydantic import BaseModel, Field

from app.schemas.common import VerificationStatus
from app.schemas.source_citation import SourceCitation


class VisaStamp(BaseModel):
    """The physical visa stamp/sticker in the passport, issued by a U.S.
    consulate or embassy.

    A valid visa permits the holder to request admission at a U.S. port of
    entry; it does not guarantee admission or determine authorized stay.
    It must never be presented as the expiration of status or employment
    authorization. A visa can expire while status (e.g. F-1 D/S) remains
    fully valid; conversely, a valid visa does not extend status.
    """

    id: str
    user_id: str
    visa_class: str = Field(..., description="Visa classification printed on the stamp, e.g. 'F-1'")
    issue_date: date
    expiration_date: date = Field(
        ...,
        description="Days until the visa stamp expires. A valid visa permits the holder to request "
        "admission at a U.S. port of entry; it does not guarantee admission or determine authorized "
        "stay. Does NOT represent the expiration of authorized stay in the U.S.",
    )
    issuing_post: str | None = Field(None, description="Consulate/embassy that issued the visa")
    entries: str | None = Field(None, description="Number of entries permitted, e.g. 'M' for multiple")
    source: SourceCitation | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
