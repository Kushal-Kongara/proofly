"""Document vault endpoint tests. Supermemory is always mocked here via a
fake service injected through FastAPI's dependency override — no test in
this file makes a network call or consumes Supermemory API credits.
"""

import hashlib

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.documents import get_supermemory_service
from app.schemas.vault_document import DocumentProcessingStatus, VaultDocument
from app.services.supermemory_service import (
    SupermemoryConfigurationError,
    SupermemoryConflictError,
    SupermemoryUpstreamError,
)

PDF_BYTES = b"%PDF-1.4\n%synthetic demo content\n%%EOF"


class FakeSupermemoryService:
    def __init__(
        self,
        *,
        upload_result: VaultDocument | None = None,
        upload_exception: Exception | None = None,
        list_result: list[VaultDocument] | None = None,
        delete_exception: Exception | None = None,
    ) -> None:
        self.upload_result = upload_result
        self.upload_exception = upload_exception
        self.list_result = list_result or []
        self.delete_exception = delete_exception
        self.upload_calls: list[dict] = []
        self.delete_calls: list[str] = []

    async def upload_document(self, **kwargs) -> VaultDocument:
        self.upload_calls.append(kwargs)
        if self.upload_exception:
            raise self.upload_exception
        assert self.upload_result is not None
        return self.upload_result

    async def list_documents(self) -> list[VaultDocument]:
        return self.list_result

    async def get_document_status(self, document_id: str) -> VaultDocument:
        raise NotImplementedError

    async def delete_document(self, document_id: str) -> None:
        self.delete_calls.append(document_id)
        if self.delete_exception:
            raise self.delete_exception


@pytest.fixture
def client():
    return TestClient(app)


def _override(fake_service: FakeSupermemoryService):
    app.dependency_overrides[get_supermemory_service] = lambda: fake_service
    yield fake_service
    app.dependency_overrides.pop(get_supermemory_service, None)


@pytest.fixture
def fake_service():
    yield from _override(FakeSupermemoryService())


def test_upload_document_success(client: TestClient, fake_service: FakeSupermemoryService):
    fake_service.upload_result = VaultDocument(
        id="sm_doc_1",
        custom_id="proofly_abc123",
        filename="Maya_Patel_Resume.pdf",
        content_type="application/pdf",
        status=DocumentProcessingStatus.QUEUED,
        metadata={"original_filename": "Maya_Patel_Resume.pdf", "synthetic": True},
    )

    response = client.post(
        "/api/documents/upload",
        files={"file": ("Maya_Patel_Resume.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "sm_doc_1"
    assert body["status"] == "queued"

    assert len(fake_service.upload_calls) == 1
    call = fake_service.upload_calls[0]
    expected_custom_id = "proofly_" + hashlib.sha256(PDF_BYTES).hexdigest()[:32]
    assert call["custom_id"] == expected_custom_id
    assert call["metadata"]["original_filename"] == "Maya_Patel_Resume.pdf"
    assert call["metadata"]["content_type"] == "application/pdf"
    assert call["metadata"]["source"] == "manual_upload"
    assert call["metadata"]["synthetic"] is True


def test_upload_invalid_extension(client: TestClient, fake_service: FakeSupermemoryService):
    response = client.post(
        "/api/documents/upload",
        files={"file": ("notes.txt", b"plain text content", "text/plain")},
    )

    assert response.status_code == 400
    assert fake_service.upload_calls == []


def test_upload_invalid_mime_type(client: TestClient, fake_service: FakeSupermemoryService):
    # .pdf extension but a declared content type that doesn't match it.
    response = client.post(
        "/api/documents/upload",
        files={"file": ("fake.pdf", PDF_BYTES, "text/plain")},
    )

    assert response.status_code == 400
    assert fake_service.upload_calls == []


def test_upload_empty_file(client: TestClient, fake_service: FakeSupermemoryService):
    response = client.post(
        "/api/documents/upload",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    assert fake_service.upload_calls == []


def test_upload_file_too_large(client: TestClient, fake_service: FakeSupermemoryService):
    oversized = b"%PDF-1.4\n" + (b"0" * (10 * 1024 * 1024 + 1))
    response = client.post(
        "/api/documents/upload",
        files={"file": ("big.pdf", oversized, "application/pdf")},
    )

    assert response.status_code == 413
    assert fake_service.upload_calls == []


def test_upload_missing_api_key_returns_503(client: TestClient, fake_service: FakeSupermemoryService):
    fake_service.upload_exception = SupermemoryConfigurationError("SUPERMEMORY_API_KEY is not configured")

    response = client.post(
        "/api/documents/upload",
        files={"file": ("Maya_Patel_Resume.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 503
    # Never leak configuration/secret details in the response body.
    assert "SUPERMEMORY_API_KEY" not in response.text


def test_upload_upstream_failure_returns_502(client: TestClient, fake_service: FakeSupermemoryService):
    fake_service.upload_exception = SupermemoryUpstreamError("Supermemory upstream request failed (status 500)")

    response = client.post(
        "/api/documents/upload",
        files={"file": ("Maya_Patel_Resume.pdf", PDF_BYTES, "application/pdf")},
    )

    assert response.status_code == 502


def test_list_documents_returns_only_fake_services_documents(client: TestClient, fake_service: FakeSupermemoryService):
    fake_service.list_result = [
        VaultDocument(
            id="sm_doc_1",
            filename="Maya_Patel_Resume.pdf",
            content_type="application/pdf",
            status=DocumentProcessingStatus.DONE,
        )
    ]

    response = client.get("/api/documents")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == "sm_doc_1"


def test_delete_document_while_processing_returns_409(client: TestClient, fake_service: FakeSupermemoryService):
    fake_service.delete_exception = SupermemoryConflictError(
        "Document is still processing. Try deleting it after processing finishes."
    )

    response = client.delete("/api/documents/sm_doc_1")

    assert response.status_code == 409
    body = response.json()
    assert body["detail"] == "Document is still processing. Try deleting it after processing finishes."
    # Never leak the raw upstream SDK error.
    assert "ConflictError" not in response.text
    assert "supermemory" not in response.text.lower()
    assert fake_service.delete_calls == ["sm_doc_1"]


def test_delete_document_success_returns_204(client: TestClient, fake_service: FakeSupermemoryService):
    response = client.delete("/api/documents/sm_doc_1")

    assert response.status_code == 204
    assert fake_service.delete_calls == ["sm_doc_1"]
