from pydantic import BaseModel, Field


class SourceCitation(BaseModel):
    """Points an AI-derived fact back to the exact document (and page) it came from."""

    document_id: str = Field(..., description="ID of the ImmigrationDocument this fact was extracted from")
    page_number: int | None = Field(None, description="Page number within the document, when known")
    excerpt: str | None = Field(None, description="Short verbatim snippet supporting the fact")
