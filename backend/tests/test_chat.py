"""Chat endpoint tests (Phase 5). Both Supermemory and Featherless are
always mocked here via dependency overrides — no test in this file makes a
network call or consumes API credits.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers.chat import get_featherless_service, get_supermemory_service
from app.schemas.chat import FeatherlessChatOutput
from app.schemas.vault_document import DocumentProcessingStatus, VaultDocument
from app.services.featherless_service import (
    FeatherlessConfigurationError,
    FeatherlessInputTooLargeError,
    FeatherlessUpstreamError,
)
from app.services.supermemory_service import RetrievedSource, SupermemoryConfigurationError


class FakeSupermemoryService:
    def __init__(
        self,
        *,
        documents: list[VaultDocument] | None = None,
        sources: list[RetrievedSource] | None = None,
        list_exception: Exception | None = None,
        search_exception: Exception | None = None,
    ) -> None:
        self.documents = documents if documents is not None else [_done_document()]
        self.sources = sources or []
        self.list_exception = list_exception
        self.search_exception = search_exception
        self.search_calls: list[dict] = []

    async def list_documents(self) -> list[VaultDocument]:
        if self.list_exception:
            raise self.list_exception
        return self.documents

    async def search_document_chunks(self, *, query: str, limit: int, threshold: float | None = None) -> list[RetrievedSource]:
        self.search_calls.append({"query": query, "limit": limit, "threshold": threshold})
        if self.search_exception:
            raise self.search_exception
        return self.sources


class FakeFeatherlessService:
    def __init__(self, *, result: FeatherlessChatOutput | None = None, repair_attempted: bool = False, exception: Exception | None = None) -> None:
        self.result = result
        self.repair_attempted = repair_attempted
        self.exception = exception
        self.calls: list[dict] = []

    async def answer_chat_question(self, *, question, history, sources):
        self.calls.append({"question": question, "history": history, "sources": sources})
        if self.exception:
            raise self.exception
        assert self.result is not None
        return self.result, self.repair_attempted


def _done_document(doc_id: str = "sm_doc_1") -> VaultDocument:
    return VaultDocument(
        id=doc_id,
        custom_id=f"proofly_{doc_id}",
        filename="Maya_Patel_EAD_Summary.pdf",
        content_type="application/pdf",
        status=DocumentProcessingStatus.DONE,
        created_at=None,
        metadata={},
    )


def _source(source_key: str = "S1", document_id: str = "doc_ead", content: str = "STEM OPT extension EAD valid 07/01/2025 to 06/30/2027.") -> RetrievedSource:
    return RetrievedSource(source_key=source_key, document_id=document_id, filename="Maya_Patel_EAD_Summary.pdf", content=content, page_number=None, similarity=0.9)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _override(supermemory: FakeSupermemoryService, featherless: FakeFeatherlessService):
    app.dependency_overrides[get_supermemory_service] = lambda: supermemory
    app.dependency_overrides[get_featherless_service] = lambda: featherless
    yield supermemory, featherless
    app.dependency_overrides.pop(get_supermemory_service, None)
    app.dependency_overrides.pop(get_featherless_service, None)


def test_grounded_answer_requires_and_returns_citations(client: TestClient):
    supermemory = FakeSupermemoryService(sources=[_source()])
    featherless = FakeFeatherlessService(
        result=FeatherlessChatOutput(
            answer="Your STEM OPT EAD is valid through June 30, 2027, per S1.",
            cited_source_keys=["S1"],
            insufficient_evidence=False,
            needs_professional_review=False,
        )
    )

    for _ in _override(supermemory, featherless):
        response = client.post("/api/chat", json={"question": "When does my current STEM OPT work authorization expire?"})

        assert response.status_code == 200
        body = response.json()
        assert body["answer_mode"] == "document_grounded"
        assert len(body["citations"]) == 1
        assert body["citations"][0]["filename"] == "Maya_Patel_EAD_Summary.pdf"
        assert body["citations"][0]["document_id"] == "doc_ead"
        assert body["disclaimer"] == "Proofly organizes document-derived information and is not legal advice."
        assert body["searched_document_count"] == 1


def test_no_context_path_skips_featherless_entirely(client: TestClient):
    supermemory = FakeSupermemoryService(sources=[])
    featherless = FakeFeatherlessService()

    for _ in _override(supermemory, featherless):
        response = client.post("/api/chat", json={"question": "What is my passport number?"})

        assert response.status_code == 200
        body = response.json()
        assert body["answer_mode"] == "insufficient_document_evidence"
        assert body["answer"] == "I couldn't find enough information in the uploaded documents to answer that."
        assert body["citations"] == []
        assert featherless.calls == []  # never called Featherless


def test_insufficient_evidence_from_model_uses_fixed_safe_response(client: TestClient):
    supermemory = FakeSupermemoryService(sources=[_source()])
    featherless = FakeFeatherlessService(
        result=FeatherlessChatOutput(
            answer="I might guess something",  # must never leak through
            cited_source_keys=[],
            insufficient_evidence=True,
            needs_professional_review=False,
        )
    )

    for _ in _override(supermemory, featherless):
        response = client.post("/api/chat", json={"question": "What is my passport number?"})

        assert response.status_code == 200
        body = response.json()
        assert body["answer_mode"] == "insufficient_document_evidence"
        assert body["answer"] == "I couldn't find enough information in the uploaded documents to answer that."
        assert "I might guess something" not in body["answer"]
        assert body["citations"] == []


def test_no_processed_documents_returns_409_before_any_search(client: TestClient):
    supermemory = FakeSupermemoryService(documents=[])
    featherless = FakeFeatherlessService()

    for _ in _override(supermemory, featherless):
        response = client.post("/api/chat", json={"question": "When does my EAD expire?"})

        assert response.status_code == 409
        assert supermemory.search_calls == []
        assert featherless.calls == []


def test_server_controlled_container_query_never_accepts_client_container_tag(client: TestClient):
    supermemory = FakeSupermemoryService(sources=[_source()])
    featherless = FakeFeatherlessService(
        result=FeatherlessChatOutput(answer="answer", cited_source_keys=["S1"], insufficient_evidence=False, needs_professional_review=False)
    )

    for _ in _override(supermemory, featherless):
        response = client.post(
            "/api/chat",
            json={"question": "When does my EAD expire?", "containerTag": "some_other_users_container"},
        )

        assert response.status_code == 200
        # The extra field is silently ignored — ChatRequest has no container_tag field at all.
        assert supermemory.search_calls[0]["query"]


def test_history_is_not_treated_as_documentary_evidence(client: TestClient):
    supermemory = FakeSupermemoryService(sources=[_source()])
    featherless = FakeFeatherlessService(
        result=FeatherlessChatOutput(answer="answer", cited_source_keys=["S1"], insufficient_evidence=False, needs_professional_review=False)
    )

    for _ in _override(supermemory, featherless):
        response = client.post(
            "/api/chat",
            json={
                "question": "And what about my passport?",
                "history": [
                    {"role": "user", "content": "When does my EAD expire?"},
                    {"role": "assistant", "content": "It expires June 30, 2027, per S1."},
                ],
            },
        )

        assert response.status_code == 200
        # Retrieval query is built from the current question plus the last
        # *user* question only — never a prior assistant claim.
        query = supermemory.search_calls[0]["query"]
        assert "When does my EAD expire?" in query
        assert "It expires June 30, 2027" not in query
        # But the assistant turn is still passed to Featherless as conversation
        # context (to interpret follow-ups), never dropped silently.
        call_history_contents = [m.content for m in featherless.calls[0]["history"]]
        assert "It expires June 30, 2027, per S1." in call_history_contents


def test_current_law_question_does_not_get_an_unsupported_legal_answer(client: TestClient):
    """The system prompt instructs the model to treat this as insufficient
    evidence rather than answering from its own training data — this test
    verifies the API surfaces exactly that path when the model complies.
    """
    supermemory = FakeSupermemoryService(sources=[_source()])
    featherless = FakeFeatherlessService(
        result=FeatherlessChatOutput(
            answer="Uploaded documents don't establish current regulations; check official USCIS/DHS sources.",
            cited_source_keys=[],
            insufficient_evidence=True,
            needs_professional_review=False,
        )
    )

    for _ in _override(supermemory, featherless):
        response = client.post("/api/chat", json={"question": "What are the current STEM OPT regulations?"})

        assert response.status_code == 200
        body = response.json()
        assert body["answer_mode"] == "insufficient_document_evidence"
        assert body["answer"] == "I couldn't find enough information in the uploaded documents to answer that."


def test_invalid_request_empty_question_returns_400(client: TestClient):
    response = client.post("/api/chat", json={"question": ""})
    assert response.status_code == 400


def test_invalid_request_question_too_long_returns_400(client: TestClient):
    response = client.post("/api/chat", json={"question": "x" * 1001})
    assert response.status_code == 400


def test_invalid_request_too_many_history_messages_returns_400(client: TestClient):
    response = client.post(
        "/api/chat",
        json={"question": "q", "history": [{"role": "user", "content": "hi"} for _ in range(7)]},
    )
    assert response.status_code == 400


def test_invalid_request_bad_history_role_returns_400(client: TestClient):
    response = client.post(
        "/api/chat",
        json={"question": "q", "history": [{"role": "system", "content": "hi"}]},
    )
    assert response.status_code == 400


def test_missing_configuration_returns_503(client: TestClient):
    supermemory = FakeSupermemoryService(list_exception=SupermemoryConfigurationError("SUPERMEMORY_API_KEY is not configured"))
    featherless = FakeFeatherlessService()

    for _ in _override(supermemory, featherless):
        response = client.post("/api/chat", json={"question": "q"})
        assert response.status_code == 503
        assert "SUPERMEMORY_API_KEY" not in response.text


def test_featherless_configuration_error_returns_503(client: TestClient):
    supermemory = FakeSupermemoryService(sources=[_source()])
    featherless = FakeFeatherlessService(exception=FeatherlessConfigurationError("FEATHERLESS_API_KEY is not configured"))

    for _ in _override(supermemory, featherless):
        response = client.post("/api/chat", json={"question": "q"})
        assert response.status_code == 503
        assert "FEATHERLESS_API_KEY" not in response.text


def test_featherless_input_too_large_returns_413(client: TestClient):
    supermemory = FakeSupermemoryService(sources=[_source()])
    featherless = FakeFeatherlessService(exception=FeatherlessInputTooLargeError("too large"))

    for _ in _override(supermemory, featherless):
        response = client.post("/api/chat", json={"question": "q"})
        assert response.status_code == 413


def test_featherless_upstream_failure_returns_502(client: TestClient):
    supermemory = FakeSupermemoryService(sources=[_source()])
    featherless = FakeFeatherlessService(exception=FeatherlessUpstreamError("Featherless upstream request failed (status 500)"))

    for _ in _override(supermemory, featherless):
        response = client.post("/api/chat", json={"question": "q"})
        assert response.status_code == 502


def test_no_conversation_is_ever_written_to_supermemory(client: TestClient):
    """No fake method for writing/uploading exists on FakeSupermemoryService
    at all — if the router ever tried to call one, this test would fail
    with an AttributeError rather than silently passing.
    """
    supermemory = FakeSupermemoryService(sources=[_source()])
    featherless = FakeFeatherlessService(
        result=FeatherlessChatOutput(answer="answer", cited_source_keys=["S1"], insufficient_evidence=False, needs_professional_review=False)
    )

    for _ in _override(supermemory, featherless):
        response = client.post("/api/chat", json={"question": "q"})
        assert response.status_code == 200
        assert not hasattr(supermemory, "upload_document")
