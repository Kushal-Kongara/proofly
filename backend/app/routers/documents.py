"""Document vault endpoints: synthetic-demo document upload and management,
backed by Supermemory. Files are never written to disk on this server —
each upload is read into memory, forwarded to Supermemory, and discarded.
"""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.config import settings
from app.schemas.vault_document import VaultDocument
from app.services.supermemory_service import (
    SupermemoryConfigurationError,
    SupermemoryConflictError,
    SupermemoryNotFoundError,
    SupermemoryService,
    SupermemoryUpstreamError,
    get_supermemory_service,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])

# extension -> allowed declared MIME type(s). Both must match for a file to be accepted.
_ALLOWED_TYPES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
}


def _extension_of(filename: str) -> str:
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def _validate_upload(filename: str, content_type: str | None, size: int) -> None:
    if size == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    if size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_size_bytes // (1024 * 1024)} MB upload limit",
        )

    extension = _extension_of(filename)
    if extension not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file extension. Accepted: PDF, PNG, JPG, JPEG",
        )

    if content_type not in _ALLOWED_TYPES[extension]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content type does not match its extension",
        )


def _handle_service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, SupermemoryConfigurationError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document storage is not configured",
        )
    if isinstance(exc, SupermemoryNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if isinstance(exc, SupermemoryConflictError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, SupermemoryUpstreamError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Document storage upstream error")
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unexpected document storage error")


@router.post("/upload", response_model=VaultDocument, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    service: SupermemoryService = Depends(get_supermemory_service),
) -> VaultDocument:
    content = await file.read()
    _validate_upload(file.filename or "", file.content_type, len(content))

    custom_id = "proofly_" + hashlib.sha256(content).hexdigest()[:32]

    try:
        return await service.upload_document(
            file_bytes=content,
            filename=file.filename or custom_id,
            content_type=file.content_type or "application/octet-stream",
            custom_id=custom_id,
            metadata={
                "original_filename": file.filename or "",
                "content_type": file.content_type or "",
                "source": "manual_upload",
                "synthetic": True,
            },
        )
    except (SupermemoryConfigurationError, SupermemoryUpstreamError) as exc:
        raise _handle_service_error(exc) from exc


@router.get("", response_model=list[VaultDocument])
async def list_documents(
    service: SupermemoryService = Depends(get_supermemory_service),
) -> list[VaultDocument]:
    try:
        return await service.list_documents()
    except (SupermemoryConfigurationError, SupermemoryUpstreamError) as exc:
        raise _handle_service_error(exc) from exc


@router.get("/{document_id}/status", response_model=VaultDocument)
async def get_document_status(
    document_id: str,
    service: SupermemoryService = Depends(get_supermemory_service),
) -> VaultDocument:
    try:
        return await service.get_document_status(document_id)
    except (SupermemoryConfigurationError, SupermemoryNotFoundError, SupermemoryUpstreamError) as exc:
        raise _handle_service_error(exc) from exc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_document(
    document_id: str,
    service: SupermemoryService = Depends(get_supermemory_service),
) -> None:
    """Delete a single document by ID. Never deletes the container.

    Returns 409 if Supermemory reports the document is still processing
    (it can't be deleted mid-pipeline) — retry after its status reaches
    'done' or 'failed'. Returns 404 if the ID doesn't exist.
    """
    try:
        await service.delete_document(document_id)
    except (
        SupermemoryConfigurationError,
        SupermemoryNotFoundError,
        SupermemoryConflictError,
        SupermemoryUpstreamError,
    ) as exc:
        raise _handle_service_error(exc) from exc
