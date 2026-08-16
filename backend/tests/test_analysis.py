"""Analysis endpoint tests. Both Supermemory and Featherless are always
mocked here via dependency overrides — no test in this file makes a
network call or consumes API credits.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import routers
from app.main import app
from app.routers.analysis import get_featherless_service, get_supermemory_service
from app.schemas.analysis import (
    AnalyzedDocument,
    EmploymentAuthorizationRecord,
    EmploymentAuthorizationType,
    LLMAnalysisOutput,
)
from app.services.featherless_service import (
    FeatherlessConfigurationError,
    FeatherlessInputTooLargeError,
    FeatherlessUpstreamError,
)
from app.services.supermemory_service import RetrievedDocument, SupermemoryConfigurationError


class FakeSupermemoryService:
    def __init__(self, *, documents: list[RetrievedDocument] | None = None, exception: Exception | None = None) -> None:
        self.documents = documents or []
        self.exception = exception

    async def list_completed_documents_with_content(self) -> list[RetrievedDocument]:
        if self.exception:
            raise self.exception
        return self.documents


class FakeFeatherlessService:
    def __init__(self, *, result: LLMAnalysisOutput | None = None, exception: Exception | None = None) -> None:
        self.result = result
        self.exception = exception
        self.calls: list[list[RetrievedDocument]] = []

    async def analyze_documents(self, documents: list[RetrievedDocument]) -> LLMAnalysisOutput:
        self.calls.append(documents)
        if self.exception:
            raise self.exception
        assert self.result is not None
        return self.result


@pytest.fixture(autouse=True)
def reset_in_process_store():
    routers.analysis._latest_analysis = None
    yield
    routers.analysis._latest_analysis = None


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _override(supermemory: FakeSupermemoryService, featherless: FakeFeatherlessService):
    app.dependency_overrides[get_supermemory_service] = lambda: supermemory
    app.dependency_overrides[get_featherless_service] = lambda: featherless
    yield supermemory, featherless
    app.dependency_overrides.pop(get_supermemory_service, None)
    app.dependency_overrides.pop(get_featherless_service, None)


def _one_completed_document() -> RetrievedDocument:
    return RetrievedDocument(
        document_id="doc_ead",
        filename="Maya_Patel_EAD_Summary.pdf",
        content_type="application/pdf",
        content="STEM OPT extension EAD valid 07/01/2025 to 06/30/2027.",
    )


def _llm_output_with_ead() -> LLMAnalysisOutput:
    return LLMAnalysisOutput(
        analyzed_documents=[
            AnalyzedDocument(document_id="doc_ead", filename="Maya_Patel_EAD_Summary.pdf", document_type="ead", facts=[])
        ],
        employment_authorizations=[
            EmploymentAuthorizationRecord(
                authorization_type=EmploymentAuthorizationType.STEM_OPT_EXTENSION,
                start_date=date(2025, 7, 1),
                end_date=date(2027, 6, 30),
                source_document_id="doc_ead",
                source_filename="Maya_Patel_EAD_Summary.pdf",
                confidence=0.95,
            )
        ],
    )


def test_run_analysis_success(client: TestClient):
    supermemory = FakeSupermemoryService(documents=[_one_completed_document()])
    featherless = FakeFeatherlessService(result=_llm_output_with_ead())

    for _ in _override(supermemory, featherless):
        response = client.post("/api/analysis/run")

        assert response.status_code == 201
        body = response.json()
        assert len(body["analyzed_documents"]) == 1
        assert len(body["employment_authorizations"]) == 1
        assert len(body["timeline"]) == 1
        assert body["timeline"][0]["category"] == "work_authorization"
        assert "as_of_date" in body
        assert len(featherless.calls) == 1


def test_run_analysis_with_no_completed_documents_returns_409_and_creates_nothing(client: TestClient):
    supermemory = FakeSupermemoryService(documents=[])
    featherless = FakeFeatherlessService(result=_llm_output_with_ead())

    for _ in _override(supermemory, featherless):
        response = client.post("/api/analysis/run")

        assert response.status_code == 409
        assert response.json()["detail"] == "No processed documents are available for analysis."
        assert featherless.calls == []

        # Nothing was stored — the in-process "latest" stays empty.
        assert client.get("/api/analysis/latest").status_code == 404
        assert client.get("/api/timeline").status_code == 404


def test_get_latest_analysis_returns_404_before_any_run(client: TestClient):
    response = client.get("/api/analysis/latest")
    assert response.status_code == 404


def test_get_latest_analysis_returns_stored_result_after_run(client: TestClient):
    supermemory = FakeSupermemoryService(documents=[_one_completed_document()])
    featherless = FakeFeatherlessService(result=_llm_output_with_ead())

    for _ in _override(supermemory, featherless):
        run_response = client.post("/api/analysis/run")
        latest_response = client.get("/api/analysis/latest")

        assert latest_response.status_code == 200
        assert latest_response.json() == run_response.json()


def test_get_timeline_returns_404_before_any_run(client: TestClient):
    response = client.get("/api/timeline")
    assert response.status_code == 404


def test_get_timeline_returns_stored_timeline_after_run(client: TestClient):
    supermemory = FakeSupermemoryService(documents=[_one_completed_document()])
    featherless = FakeFeatherlessService(result=_llm_output_with_ead())

    for _ in _override(supermemory, featherless):
        client.post("/api/analysis/run")
        response = client.get("/api/timeline")

        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["category"] == "work_authorization"


def test_missing_featherless_configuration_returns_503(client: TestClient):
    supermemory = FakeSupermemoryService(documents=[_one_completed_document()])
    featherless = FakeFeatherlessService(exception=FeatherlessConfigurationError("FEATHERLESS_API_KEY is not configured"))

    for _ in _override(supermemory, featherless):
        response = client.post("/api/analysis/run")

        assert response.status_code == 503
        assert "FEATHERLESS_API_KEY" not in response.text


def test_missing_supermemory_configuration_returns_503(client: TestClient):
    supermemory = FakeSupermemoryService(exception=SupermemoryConfigurationError("SUPERMEMORY_API_KEY is not configured"))
    featherless = FakeFeatherlessService(result=_llm_output_with_ead())

    for _ in _override(supermemory, featherless):
        response = client.post("/api/analysis/run")

        assert response.status_code == 503
        assert featherless.calls == []


def test_featherless_upstream_failure_returns_502(client: TestClient):
    supermemory = FakeSupermemoryService(documents=[_one_completed_document()])
    featherless = FakeFeatherlessService(exception=FeatherlessUpstreamError("Featherless upstream request failed (status 500)"))

    for _ in _override(supermemory, featherless):
        response = client.post("/api/analysis/run")
        assert response.status_code == 502


def test_featherless_input_too_large_returns_413(client: TestClient):
    supermemory = FakeSupermemoryService(documents=[_one_completed_document()])
    featherless = FakeFeatherlessService(exception=FeatherlessInputTooLargeError("too large"))

    for _ in _override(supermemory, featherless):
        response = client.post("/api/analysis/run")
        assert response.status_code == 413
