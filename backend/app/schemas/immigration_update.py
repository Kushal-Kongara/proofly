"""Official immigration updates search (Phase 6) data contracts.

Proofly searches current official government sources (`app/data/
immigration_updates.py::OFFICIAL_DOMAINS`) via Tavily and displays the
resulting links/snippets. This is awareness only — a result is never
claimed to change the user's case, and search snippets are never converted
into personalized legal advice or an "urgent" label. See
`docs/ARCHITECTURE.md` and `app/services/tavily_service.py`.
"""

from __future__ import annotations

from datetime import date as date_
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

MAX_SNIPPET_LENGTH = 300


class UpdateCategory(str, Enum):
    """The only categories the browser may request — each maps to exactly
    one fixed, server-owned Tavily query (`CATEGORY_QUERIES`). There is no
    field anywhere a client can use to send a free-text search query.
    """

    F1_OPT = "f1_opt"
    O1A = "o1a"
    GENERAL = "general"


class UpdateTimeRange(str, Enum):
    MONTH = "month"
    YEAR = "year"


class ImmigrationUpdateResult(BaseModel):
    """One server-validated, normalized official-source search result.
    Every field here is computed/validated in Python
    (`app/services/tavily_service.py`) — never taken from Tavily unchecked.
    """

    id: str
    title: str
    url: str
    official_domain: str
    snippet: str = Field(..., max_length=MAX_SNIPPET_LENGTH)
    relevance_score: float | None = None
    published_date: date_ | None = None
    category: UpdateCategory
    source_type: str = "official_government"
    retrieved_at: datetime


class UpdatesResponse(BaseModel):
    category: UpdateCategory
    time_range: UpdateTimeRange
    results: list[ImmigrationUpdateResult]
    official_domains: list[str]
    retrieved_at: datetime
    cache_hit: bool
    disclaimer: str
