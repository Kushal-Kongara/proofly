"""Official immigration updates endpoint tests (Phase 6). TavilyService is
always mocked here via dependency override — no test in this file makes a
network call or consumes a Tavily credit.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.data.immigration_updates import OFFICIAL_DOMAINS, UPDATES_DISCLAIMER
from app.main import app
from app.routers.updates import get_tavily_service
from app.schemas.immigration_update import ImmigrationUpdateResult, UpdateCategory, UpdateTimeRange
from app.services.tavily_service import TavilyConfigurationError, TavilyUpstreamError


class FakeTavilyService:
    def __init__(
        self,
        *,
        results: list[ImmigrationUpdateResult] | None = None,
        cache_hit: bool = False,
        retrieved_at: datetime | None = None,
        exception: Exception | None = None,
    ) -> None:
        self.results = results or []
        self.cache_hit = cache_hit
        self.retrieved_at = retrieved_at or datetime.now(timezone.utc)
        self.exception = exception
        self.calls: list[dict] = []

    async def search_updates(self, *, category: UpdateCategory, time_range: UpdateTimeRange):
        self.calls.append({"category": category, "time_range": time_range})
        if self.exception:
            raise self.exception
        return self.results, self.cache_hit, self.retrieved_at


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _override(tavily: FakeTavilyService):
    app.dependency_overrides[get_tavily_service] = lambda: tavily
    yield tavily
    app.dependency_overrides.pop(get_tavily_service, None)


def _one_result() -> ImmigrationUpdateResult:
    return ImmigrationUpdateResult(
        id="abc123",
        title="USCIS Policy Update",
        url="https://www.uscis.gov/newsroom/some-update",
        official_domain="uscis.gov",
        snippet="Some official policy update content.",
        relevance_score=0.87,
        published_date=None,
        category=UpdateCategory.GENERAL,
        retrieved_at=datetime.now(timezone.utc),
    )


def test_updates_success_returns_expected_shape(client: TestClient):
    tavily = FakeTavilyService(results=[_one_result()], cache_hit=False)

    for _ in _override(tavily):
        response = client.get("/api/updates", params={"category": "general", "time_range": "year"})

        assert response.status_code == 200
        body = response.json()
        assert body["category"] == "general"
        assert body["time_range"] == "year"
        assert len(body["results"]) == 1
        assert body["results"][0]["source_type"] == "official_government"
        assert body["official_domains"] == OFFICIAL_DOMAINS
        assert body["cache_hit"] is False
        assert body["disclaimer"] == UPDATES_DISCLAIMER
        assert tavily.calls == [{"category": UpdateCategory.GENERAL, "time_range": UpdateTimeRange.YEAR}]


def test_default_time_range_is_year(client: TestClient):
    tavily = FakeTavilyService(results=[])

    for _ in _override(tavily):
        response = client.get("/api/updates", params={"category": "f1_opt"})

        assert response.status_code == 200
        assert response.json()["time_range"] == "year"
        assert tavily.calls[0]["time_range"] == UpdateTimeRange.YEAR


def test_cache_hit_is_surfaced_in_response(client: TestClient):
    tavily = FakeTavilyService(results=[_one_result()], cache_hit=True)

    for _ in _override(tavily):
        response = client.get("/api/updates", params={"category": "o1a", "time_range": "month"})

        assert response.status_code == 200
        assert response.json()["cache_hit"] is True


def test_missing_category_returns_400(client: TestClient):
    response = client.get("/api/updates")
    assert response.status_code == 400


def test_unsupported_category_returns_400(client: TestClient):
    response = client.get("/api/updates", params={"category": "eb1"})
    assert response.status_code == 400


def test_unsupported_time_range_returns_400(client: TestClient):
    response = client.get("/api/updates", params={"category": "general", "time_range": "week"})
    assert response.status_code == 400


def test_missing_tavily_configuration_returns_503(client: TestClient):
    tavily = FakeTavilyService(exception=TavilyConfigurationError("TAVILY_API_KEY is not configured"))

    for _ in _override(tavily):
        response = client.get("/api/updates", params={"category": "general"})

        assert response.status_code == 503
        assert "TAVILY_API_KEY" not in response.text


def test_tavily_upstream_failure_returns_502(client: TestClient):
    tavily = FakeTavilyService(exception=TavilyUpstreamError("Tavily upstream request failed"))

    for _ in _override(tavily):
        response = client.get("/api/updates", params={"category": "general"})

        assert response.status_code == 502


def test_all_returned_categories_are_valid_for_all_three_category_codes(client: TestClient):
    for category in ["f1_opt", "o1a", "general"]:
        tavily = FakeTavilyService(results=[])
        for _ in _override(tavily):
            response = client.get("/api/updates", params={"category": category})
            assert response.status_code == 200
