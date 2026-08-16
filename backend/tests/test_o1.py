"""O-1A planner endpoint tests (Phase 4). Both Supermemory and Featherless
are always mocked here via dependency overrides — no test in this file
makes a network call or consumes API credits.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import routers
from app.main import app
from app.routers.o1 import get_featherless_service, get_supermemory_service
from app.schemas.common import O1CriterionCode
from app.schemas.o1_assessment import O1EvidenceItemDraft, O1EvidenceRole, O1LLMAnalysisOutput
from app.services.featherless_service import (
    FeatherlessConfigurationError,
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
    def __init__(self, *, result: O1LLMAnalysisOutput | None = None, exception: Exception | None = None) -> None:
        self.result = result
        self.exception = exception
        self.calls: list[list[RetrievedDocument]] = []

    async def analyze_o1_evidence(self, documents: list[RetrievedDocument]) -> O1LLMAnalysisOutput:
        self.calls.append(documents)
        if self.exception:
            raise self.exception
        assert self.result is not None
        return self.result


@pytest.fixture(autouse=True)
def reset_in_process_store():
    routers.o1._latest_assessment = None
    yield
    routers.o1._latest_assessment = None


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
        document_id="doc_award",
        filename="Maya_Patel_Innovation_Award.pdf",
        content_type="application/pdf",
        content="Best Emerging Researcher Award, issued November 8, 2024.",
    )


def _llm_output_with_award() -> O1LLMAnalysisOutput:
    return O1LLMAnalysisOutput(
        evidence_items=[
            O1EvidenceItemDraft(
                title="Best Emerging Researcher Award",
                factual_summary="Award notice for the Best Emerging Researcher Award, dated 2024-11-08.",
                criterion_id=O1CriterionCode.AWARDS,
                source_document_id="doc_award",
                source_filename="Maya_Patel_Innovation_Award.pdf",
                confidence=0.9,
                evidence_role=O1EvidenceRole.DIRECT_DOCUMENT,
                limitations=["Does not establish national or international recognition of the award."],
                date=date(2024, 11, 8),
            )
        ]
    )


def test_get_criteria_returns_all_eight_static_definitions(client: TestClient):
    response = client.get("/api/o1/criteria")

    assert response.status_code == 200
    body = response.json()
    assert len(body["criteria"]) == 8
    codes = {c["code"] for c in body["criteria"]}
    assert codes == {
        "awards",
        "membership",
        "published_material",
        "judging",
        "original_contribution",
        "scholarly_articles",
        "critical_employment",
        "high_remuneration",
    }
    assert "uscis.gov" in body["official_sources"][0]
    assert body["one_time_achievement"]["name"]
    assert body["comparable_evidence"]["name"]


def test_run_assessment_success(client: TestClient):
    supermemory = FakeSupermemoryService(documents=[_one_completed_document()])
    featherless = FakeFeatherlessService(result=_llm_output_with_award())

    for _ in _override(supermemory, featherless):
        response = client.post("/api/o1/assessment/run")

        assert response.status_code == 201
        body = response.json()
        assert len(body["criteria"]) == 8
        assert len(featherless.calls) == 1

        awards = next(c for c in body["criteria"] if c["definition"]["code"] == "awards")
        assert awards["status"] == "partial_support_found"


def test_run_assessment_with_no_completed_documents_returns_409_and_creates_nothing(client: TestClient):
    supermemory = FakeSupermemoryService(documents=[])
    featherless = FakeFeatherlessService(result=_llm_output_with_award())

    for _ in _override(supermemory, featherless):
        response = client.post("/api/o1/assessment/run")

        assert response.status_code == 409
        assert featherless.calls == []
        assert client.get("/api/o1/assessment/latest").status_code == 404


def test_get_latest_assessment_returns_404_before_any_run(client: TestClient):
    response = client.get("/api/o1/assessment/latest")
    assert response.status_code == 404


def test_get_latest_assessment_returns_stored_result_after_run(client: TestClient):
    supermemory = FakeSupermemoryService(documents=[_one_completed_document()])
    featherless = FakeFeatherlessService(result=_llm_output_with_award())

    for _ in _override(supermemory, featherless):
        run_response = client.post("/api/o1/assessment/run")
        latest_response = client.get("/api/o1/assessment/latest")

        assert latest_response.status_code == 200
        assert latest_response.json() == run_response.json()


def test_missing_featherless_configuration_returns_503(client: TestClient):
    supermemory = FakeSupermemoryService(documents=[_one_completed_document()])
    featherless = FakeFeatherlessService(exception=FeatherlessConfigurationError("FEATHERLESS_API_KEY is not configured"))

    for _ in _override(supermemory, featherless):
        response = client.post("/api/o1/assessment/run")

        assert response.status_code == 503
        assert "FEATHERLESS_API_KEY" not in response.text


def test_missing_supermemory_configuration_returns_503(client: TestClient):
    supermemory = FakeSupermemoryService(exception=SupermemoryConfigurationError("SUPERMEMORY_API_KEY is not configured"))
    featherless = FakeFeatherlessService(result=_llm_output_with_award())

    for _ in _override(supermemory, featherless):
        response = client.post("/api/o1/assessment/run")

        assert response.status_code == 503
        assert featherless.calls == []


def test_featherless_upstream_failure_returns_502(client: TestClient):
    supermemory = FakeSupermemoryService(documents=[_one_completed_document()])
    featherless = FakeFeatherlessService(exception=FeatherlessUpstreamError("Featherless upstream request failed (status 500)"))

    for _ in _override(supermemory, featherless):
        response = client.post("/api/o1/assessment/run")
        assert response.status_code == 502


def test_no_forbidden_language_anywhere_in_response(client: TestClient):
    supermemory = FakeSupermemoryService(documents=[_one_completed_document()])
    featherless = FakeFeatherlessService(result=_llm_output_with_award())

    for _ in _override(supermemory, featherless):
        response = client.post("/api/o1/assessment/run")
        text = response.text
        for forbidden in [
            '"eligible"',
            '"ineligible"',
            '"approved"',
            '"denied"',
            '"criterion_satisfied"',
            "approval_chance",
            "probability",
            "percentage",
        ]:
            assert forbidden not in text
