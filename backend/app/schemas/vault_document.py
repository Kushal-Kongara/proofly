from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class DocumentProcessingStatus(str, Enum):
    """Normalized Supermemory processing status.

    Supermemory's own status field can return values Proofly doesn't have a
    defined meaning for (e.g. its 'indexing' stage). Anything that doesn't
    map onto one of these normalizes to UNKNOWN rather than being passed
    through unchecked — see app/services/supermemory_service.py.
    """

    QUEUED = "queued"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    DONE = "done"
    FAILED = "failed"
    UNKNOWN = "unknown"


class VaultDocument(BaseModel):
    """A document vault entry, normalized from the Supermemory SDK response
    shape into something stable for the frontend to depend on.
    """

    id: str
    custom_id: str | None = None
    filename: str
    content_type: str
    status: DocumentProcessingStatus
    created_at: datetime | None = None
    metadata: dict[str, str | float | bool] = {}
    error: str | None = None
