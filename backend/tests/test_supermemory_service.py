"""SupermemoryService unit tests. The real supermemory.AsyncSupermemory
client is monkeypatched with an in-memory fake, so these tests never touch
the network or consume API credits.
"""

from types import SimpleNamespace

import httpx
import pytest
from supermemory import ConflictError

from app.config import Settings
from app.schemas.vault_document import DocumentProcessingStatus
from app.services import supermemory_service as sm_service
from app.services.supermemory_service import (
    SupermemoryConfigurationError,
    SupermemoryConflictError,
    SupermemoryService,
    normalize_processing_status,
)


def _memory(
    *,
    id: str,
    status: str,
    content: str | None,
    source: str | None = "manual_upload",
    container_tags: list[str] | None = None,
    filename: str = "doc.pdf",
) -> SimpleNamespace:
    metadata = {"original_filename": filename, "content_type": "application/pdf"}
    if source is not None:
        metadata["source"] = source
    return SimpleNamespace(
        id=id,
        custom_id=f"proofly_{id}",
        metadata=metadata,
        status=status,
        created_at="2026-08-10T09:10:00Z",
        title=None,
        content=content,
        container_tags=container_tags if container_tags is not None else ["proofly_demo_maya"],
    )


def _conflict_error() -> ConflictError:
    request = httpx.Request("DELETE", "https://api.supermemory.ai/v3/documents/sm_doc_1")
    response = httpx.Response(409, request=request, json={"error": "Document is still processing"})
    return ConflictError("Error code: 409", response=response, body={"error": "Document is still processing"})


class FakeDocumentsResource:
    def __init__(self) -> None:
        self.upload_file_calls: list[dict] = []
        self.list_calls: list[dict] = []
        self.delete_calls: list[str] = []
        self.delete_exception: Exception | None = None

    async def upload_file(self, **kwargs):
        self.upload_file_calls.append(kwargs)
        return SimpleNamespace(id="sm_doc_new", status="queued")

    async def delete(self, document_id: str, **kwargs):
        self.delete_calls.append(document_id)
        if self.delete_exception:
            raise self.delete_exception

    async def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return SimpleNamespace(
            memories=[
                SimpleNamespace(
                    id="sm_doc_1",
                    custom_id="proofly_abc",
                    metadata={"original_filename": "Maya_Patel_Resume.pdf", "content_type": "application/pdf"},
                    status="done",
                    created_at="2026-08-10T09:10:00Z",
                    title=None,
                )
            ],
            pagination=SimpleNamespace(current_page=1, total_items=1, total_pages=1, limit=10),
        )


class FakeAsyncSupermemory:
    """Stands in for supermemory.AsyncSupermemory. Records the api_key it
    was constructed with so tests can assert it came from settings.
    """

    last_instance: "FakeAsyncSupermemory | None" = None

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.documents = FakeDocumentsResource()
        FakeAsyncSupermemory.last_instance = self


@pytest.fixture(autouse=True)
def patch_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sm_service, "AsyncSupermemory", FakeAsyncSupermemory)
    FakeAsyncSupermemory.last_instance = None
    yield


def _settings(**overrides) -> Settings:
    base = {
        "supermemory_api_key": "sm_test_key",
        "supermemory_container_tag": "proofly_demo_maya",
    }
    base.update(overrides)
    return Settings(**base)


@pytest.mark.anyio
async def test_upload_document_uses_server_controlled_container_and_superrag():
    service = SupermemoryService(settings=_settings())

    result = await service.upload_document(
        file_bytes=b"%PDF-1.4",
        filename="Maya_Patel_Resume.pdf",
        content_type="application/pdf",
        custom_id="proofly_hash123",
        metadata={"original_filename": "Maya_Patel_Resume.pdf", "synthetic": True},
    )

    assert result.id == "sm_doc_new"
    assert result.status == DocumentProcessingStatus.QUEUED

    call = FakeAsyncSupermemory.last_instance.documents.upload_file_calls[0]
    assert call["container_tag"] == "proofly_demo_maya"
    assert call["task_type"] == "superrag"
    assert call["custom_id"] == "proofly_hash123"
    assert '"synthetic": true' in call["metadata"]  # JSON-encoded string, not a dict


@pytest.mark.anyio
async def test_list_documents_scoped_to_server_controlled_container_only():
    service = SupermemoryService(settings=_settings())

    documents = await service.list_documents()

    call = FakeAsyncSupermemory.last_instance.documents.list_calls[0]
    assert call["container_tags"] == ["proofly_demo_maya"]
    assert len(documents) == 1
    assert documents[0].filename == "Maya_Patel_Resume.pdf"
    assert documents[0].status == DocumentProcessingStatus.DONE


@pytest.mark.anyio
async def test_missing_api_key_raises_configuration_error_without_constructing_client():
    service = SupermemoryService(settings=_settings(supermemory_api_key=None))

    with pytest.raises(SupermemoryConfigurationError):
        await service.list_documents()

    # The fake client must never have been constructed — no attempted call at all.
    assert FakeAsyncSupermemory.last_instance is None


@pytest.mark.anyio
async def test_delete_while_processing_maps_conflict_to_supermemory_conflict_error(
    monkeypatch: pytest.MonkeyPatch,
):
    # _client() constructs a fresh client per call, so the exception has to be
    # baked into the class the service will instantiate, not into an instance
    # created ahead of time.
    class ConflictingAsyncSupermemory(FakeAsyncSupermemory):
        def __init__(self, api_key: str) -> None:
            super().__init__(api_key=api_key)
            self.documents.delete_exception = _conflict_error()

    monkeypatch.setattr(sm_service, "AsyncSupermemory", ConflictingAsyncSupermemory)
    service = SupermemoryService(settings=_settings())

    with pytest.raises(SupermemoryConflictError) as exc_info:
        await service.delete_document("sm_doc_1")

    assert str(exc_info.value) == "Document is still processing. Try deleting it after processing finishes."
    # The safe message must not leak the raw SDK exception's own text/class.
    assert "ConflictError" not in str(exc_info.value)
    assert "Error code: 409" not in str(exc_info.value)


@pytest.mark.anyio
async def test_list_completed_documents_with_content_filters_correctly(monkeypatch: pytest.MonkeyPatch):
    memories = [
        _memory(id="done_doc", status="done", content="extracted text here"),
        _memory(id="queued_doc", status="queued", content=None),
        _memory(id="no_content_doc", status="done", content=""),
        _memory(id="derived_doc", status="done", content="should be ignored", source="derived_analysis"),
        _memory(id="wrong_container_doc", status="done", content="should be ignored", container_tags=["some_other_container"]),
        _memory(id="legacy_doc", status="done", content="no source key set", source=None),
    ]

    class MultiDocDocumentsResource(FakeDocumentsResource):
        async def list(self, **kwargs):
            self.list_calls.append(kwargs)
            return SimpleNamespace(memories=memories, pagination=SimpleNamespace(current_page=1, total_items=len(memories), total_pages=1, limit=10))

    class MultiDocAsyncSupermemory(FakeAsyncSupermemory):
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
            self.documents = MultiDocDocumentsResource()
            FakeAsyncSupermemory.last_instance = self

    monkeypatch.setattr(sm_service, "AsyncSupermemory", MultiDocAsyncSupermemory)
    service = SupermemoryService(settings=_settings())

    retrieved = await service.list_completed_documents_with_content()

    ids = {doc.document_id for doc in retrieved}
    assert ids == {"done_doc", "legacy_doc"}
    done = next(doc for doc in retrieved if doc.document_id == "done_doc")
    assert done.content == "extracted text here"
    assert done.filename == "doc.pdf"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("queued", DocumentProcessingStatus.QUEUED),
        ("extracting", DocumentProcessingStatus.EXTRACTING),
        ("chunking", DocumentProcessingStatus.CHUNKING),
        ("embedding", DocumentProcessingStatus.EMBEDDING),
        ("done", DocumentProcessingStatus.DONE),
        ("failed", DocumentProcessingStatus.FAILED),
        ("unknown", DocumentProcessingStatus.UNKNOWN),
        ("indexing", DocumentProcessingStatus.UNKNOWN),  # Supermemory-only stage, not in our set
        ("something_new_and_unrecognized", DocumentProcessingStatus.UNKNOWN),
        (None, DocumentProcessingStatus.UNKNOWN),
    ],
)
def test_normalize_processing_status(raw, expected):
    assert normalize_processing_status(raw) == expected
