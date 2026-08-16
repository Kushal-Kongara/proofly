"""Thin async facade over the Supermemory SDK (supermemory==3.59.0),
scoped to Proofly's single server-controlled demo container.

Kept behind SupermemoryService so FastAPI routes depend on it via
`Depends(get_supermemory_service)` and tests can override that dependency
with a fake implementation — no test ever needs a real API key or makes a
network call.
"""

from __future__ import annotations

import json
from datetime import datetime

from pydantic import BaseModel
from supermemory import AsyncSupermemory
from supermemory import APIError, ConflictError, NotFoundError

from app.config import Settings
from app.config import settings as default_settings
from app.schemas.chat import RetrievedSource
from app.schemas.vault_document import DocumentProcessingStatus, VaultDocument


class RetrievedDocument(BaseModel):
    """A completed document's extracted text content, ready to hand to the
    Featherless extraction service. Never persisted, never logged in full.
    """

    document_id: str
    filename: str
    content_type: str
    content: str

_STATUS_MAP: dict[str, DocumentProcessingStatus] = {
    "queued": DocumentProcessingStatus.QUEUED,
    "extracting": DocumentProcessingStatus.EXTRACTING,
    "chunking": DocumentProcessingStatus.CHUNKING,
    "embedding": DocumentProcessingStatus.EMBEDDING,
    "done": DocumentProcessingStatus.DONE,
    "failed": DocumentProcessingStatus.FAILED,
}


def normalize_processing_status(raw: str | None) -> DocumentProcessingStatus:
    """Maps a raw Supermemory status string onto Proofly's closed status set.

    Anything Supermemory returns that isn't one of our known values —
    including its own 'unknown' and 'indexing' stage — normalizes to
    UNKNOWN rather than being passed through unchecked.
    """
    if raw is None:
        return DocumentProcessingStatus.UNKNOWN
    return _STATUS_MAP.get(raw, DocumentProcessingStatus.UNKNOWN)


class SupermemoryConfigurationError(RuntimeError):
    """Raised when SUPERMEMORY_API_KEY is not configured."""


class SupermemoryNotFoundError(RuntimeError):
    """Raised when a document ID doesn't exist in Supermemory."""


class SupermemoryConflictError(RuntimeError):
    """Raised when Supermemory rejects an operation due to document state
    (e.g. deleting a document that hasn't finished processing yet).
    """


class SupermemoryUpstreamError(RuntimeError):
    """Raised when the Supermemory API call itself fails (network/5xx/auth)."""


def _sanitized_upstream_message(exc: Exception) -> str:
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        return f"Supermemory upstream request failed (status {status_code})"
    return "Supermemory upstream request failed"


class SupermemoryService:
    """Server-side facade over the Supermemory SDK.

    Every call is scoped to `settings.supermemory_container_tag`. Callers
    (routes) never accept a container tag from the browser, so nothing a
    client sends can read or write outside the demo container.
    """

    def __init__(self, settings: Settings = default_settings) -> None:
        self._settings = settings

    def _client(self) -> AsyncSupermemory:
        if not self._settings.supermemory_api_key:
            raise SupermemoryConfigurationError("SUPERMEMORY_API_KEY is not configured")
        return AsyncSupermemory(api_key=self._settings.supermemory_api_key)

    async def upload_document(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        custom_id: str,
        metadata: dict[str, str | bool],
    ) -> VaultDocument:
        client = self._client()
        try:
            response = await client.documents.upload_file(
                file=(filename, file_bytes, content_type),
                container_tag=self._settings.supermemory_container_tag,
                custom_id=custom_id,
                metadata=json.dumps(metadata),
                mime_type=content_type,
                task_type="superrag",
            )
        except APIError as exc:
            raise SupermemoryUpstreamError(_sanitized_upstream_message(exc)) from exc

        return VaultDocument(
            id=response.id,
            custom_id=custom_id,
            filename=filename,
            content_type=content_type,
            status=normalize_processing_status(response.status),
            created_at=None,
            metadata=metadata,
        )

    async def list_documents(self) -> list[VaultDocument]:
        client = self._client()
        try:
            response = await client.documents.list(
                container_tags=[self._settings.supermemory_container_tag],
            )
        except APIError as exc:
            raise SupermemoryUpstreamError(_sanitized_upstream_message(exc)) from exc

        return [_memory_to_vault_document(memory) for memory in response.memories]

    async def get_document_status(self, document_id: str) -> VaultDocument:
        client = self._client()
        try:
            document = await client.documents.get(document_id)
        except NotFoundError as exc:
            raise SupermemoryNotFoundError(f"Document {document_id!r} not found") from exc
        except APIError as exc:
            raise SupermemoryUpstreamError(_sanitized_upstream_message(exc)) from exc

        return _document_get_response_to_vault_document(document)

    async def list_completed_documents_with_content(self) -> list[RetrievedDocument]:
        """Documents in the server-controlled demo container whose
        processing status is 'done', with their extracted text content.

        Defends in depth even though the query itself is already scoped:
        skips anything whose own `container_tags` don't include the demo
        container, and skips anything tagged as a previously derived
        analysis result rather than a manually uploaded source document.
        """
        client = self._client()
        try:
            response = await client.documents.list(
                container_tags=[self._settings.supermemory_container_tag],
                include_content=True,
            )
        except APIError as exc:
            raise SupermemoryUpstreamError(_sanitized_upstream_message(exc)) from exc

        retrieved: list[RetrievedDocument] = []
        for memory in response.memories:
            if normalize_processing_status(memory.status) != DocumentProcessingStatus.DONE:
                continue

            container_tags = getattr(memory, "container_tags", None) or []
            if container_tags and self._settings.supermemory_container_tag not in container_tags:
                continue

            metadata = _metadata_as_dict(memory.metadata)
            if metadata.get("source") not in (None, "manual_upload"):
                continue  # ignore any previously derived-analysis documents

            if not memory.content:
                continue

            retrieved.append(
                RetrievedDocument(
                    document_id=memory.id,
                    filename=str(metadata.get("original_filename") or memory.title or memory.id),
                    content_type=str(metadata.get("content_type", "application/octet-stream")),
                    content=memory.content,
                )
            )

        return retrieved

    async def search_document_chunks(
        self,
        *,
        query: str,
        limit: int,
        threshold: float | None = None,
    ) -> list[RetrievedSource]:
        """Document-mode semantic search over the server-controlled demo
        container (Phase 5 RAG retrieval) — the Python equivalent of
        `client.search.memories(q=query, container_tag=..., search_mode="documents",
        limit=limit)`. `container_tag` always comes from settings; no caller
        may override it.

        Defends in depth the same way `list_completed_documents_with_content`
        does: chunks belonging to a document tagged as anything other than a
        manually uploaded source (e.g. a future derived-analysis or chat
        write-back) are excluded. Results are deduplicated by
        (document_id, content), capped at `settings.chat_max_context_characters`
        total, and assigned source keys (S1, S2, ...) in ranked order.
        Retrieved content is never logged.
        """
        client = self._client()
        kwargs: dict[str, object] = {
            "q": query,
            "container_tag": self._settings.supermemory_container_tag,
            "search_mode": "documents",
            "limit": limit,
            "include": {"documents": True},
        }
        if threshold is not None:
            kwargs["threshold"] = threshold

        try:
            response = await client.search.memories(**kwargs)
        except APIError as exc:
            raise SupermemoryUpstreamError(_sanitized_upstream_message(exc)) from exc

        seen: set[tuple[str, str]] = set()
        sources: list[RetrievedSource] = []
        total_characters = 0

        for result in response.results:
            content = (result.chunk or "").strip()
            if not content:
                continue

            documents = getattr(result, "documents", None) or []
            if not documents:
                continue
            document = documents[0]

            doc_metadata = _metadata_as_dict(document.metadata)
            if doc_metadata.get("source") not in (None, "manual_upload"):
                continue  # exclude derived analyses, chat history, other generated content

            similarity = getattr(result, "similarity", None)
            if threshold is not None and similarity is not None and similarity < threshold:
                continue

            dedup_key = (document.id, content)
            if dedup_key in seen:
                continue

            if total_characters + len(content) > self._settings.chat_max_context_characters:
                continue  # cap total retrieved context length

            seen.add(dedup_key)
            total_characters += len(content)

            result_metadata = _metadata_as_dict(getattr(result, "metadata", None))
            page_number = _extract_page_number(result_metadata) or _extract_page_number(doc_metadata)

            sources.append(
                RetrievedSource(
                    source_key="",
                    document_id=document.id,
                    filename=str(doc_metadata.get("original_filename") or document.title or document.id),
                    content=content,
                    page_number=page_number,
                    similarity=similarity,
                )
            )

        for index, source in enumerate(sources, start=1):
            source.source_key = f"S{index}"

        return sources

    async def delete_document(self, document_id: str) -> None:
        client = self._client()
        try:
            await client.documents.delete(document_id)
        except NotFoundError as exc:
            raise SupermemoryNotFoundError(f"Document {document_id!r} not found") from exc
        except ConflictError as exc:
            raise SupermemoryConflictError(
                "Document is still processing. Try deleting it after processing finishes."
            ) from exc
        except APIError as exc:
            raise SupermemoryUpstreamError(_sanitized_upstream_message(exc)) from exc


def _parse_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _metadata_as_dict(raw: object) -> dict[str, str | float | bool]:
    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items() if isinstance(v, (str, float, bool, int))}
    return {}


def _extract_page_number(metadata: dict[str, str | float | bool]) -> int | None:
    """Only returns a page number when genuinely supplied in metadata —
    never guessed. Neither the search API's chunk-mode results nor this
    app's own ingestion pipeline is guaranteed to attach one.
    """
    for key in ("page_number", "page"):
        value = metadata.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _memory_to_vault_document(memory) -> VaultDocument:  # noqa: ANN001 - supermemory SDK model
    metadata = _metadata_as_dict(memory.metadata)
    return VaultDocument(
        id=memory.id,
        custom_id=memory.custom_id,
        filename=str(metadata.get("original_filename") or memory.title or memory.id),
        content_type=str(metadata.get("content_type", "application/octet-stream")),
        status=normalize_processing_status(memory.status),
        created_at=_parse_timestamp(memory.created_at),
        metadata=metadata,
    )


def _document_get_response_to_vault_document(document) -> VaultDocument:  # noqa: ANN001
    metadata = _metadata_as_dict(document.metadata)
    return VaultDocument(
        id=document.id,
        custom_id=document.custom_id,
        filename=metadata.get("original_filename") or document.title or document.id,
        content_type=str(metadata.get("content_type", "application/octet-stream")),
        status=normalize_processing_status(document.status),
        created_at=_parse_timestamp(document.created_at),
        metadata=metadata,
    )


def get_supermemory_service() -> SupermemoryService:
    return SupermemoryService()
