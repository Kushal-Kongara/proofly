"""Static, server-owned configuration for the official immigration updates
search (Phase 6). Never accepted from the browser — see
`app/services/tavily_service.py` and `app/routers/updates.py`.
"""

from __future__ import annotations

from app.schemas.immigration_update import UpdateCategory

# Domains treated as official U.S. government immigration sources. Passed to
# Tavily as `include_domains` (so results are already scoped upstream) and
# re-validated server-side against every returned result's hostname before
# it is ever normalized into an `ImmigrationUpdateResult` — see
# `app/services/tavily_service.py::_is_official_hostname`.
OFFICIAL_DOMAINS: list[str] = [
    "uscis.gov",
    "dhs.gov",
    "studyinthestates.dhs.gov",
    "ice.gov",
    "travel.state.gov",
    "cbp.gov",
    "federalregister.gov",
]

# Fixed server-side query per category — the browser sends a category code,
# never a free-text query, so nothing a client sends can change what Tavily
# is actually asked.
CATEGORY_QUERIES: dict[UpdateCategory, str] = {
    UpdateCategory.F1_OPT: "official F-1, OPT and STEM OPT policy/news updates",
    UpdateCategory.O1A: "official O-1A extraordinary-ability policy/news updates",
    UpdateCategory.GENERAL: "official USCIS immigration policy and form updates",
}

UPDATES_DISCLAIMER = (
    "Official-source search results are provided for awareness only. Verify the full "
    "source and consult a qualified professional before acting."
)
