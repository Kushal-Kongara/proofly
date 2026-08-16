from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import DocumentType
from app.schemas.extracted_fact import ExtractedFact


class ImmigrationDocument(BaseModel):
    """A single uploaded document belonging to a user's vault."""

    id: str
    user_id: str
    document_type: DocumentType
    filename: str
    uploaded_at: datetime
    page_count: int | None = None
    extracted_facts: list[ExtractedFact] = []
