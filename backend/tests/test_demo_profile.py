"""Validates sample_documents/demo_profile.json against the Pydantic schemas
and the corrected immigration data model for the demo reference date
(2026-08-15):

- ImmigrationStatus is a classification only (e.g. F-1) and stays current
  throughout OPT/STEM OPT — those are EmploymentAuthorization periods held
  under it, not separate statuses.
- A D/S admission has no fixed end date and must not produce a numerical
  countdown.
- Days until the visa stamp expires is its own figure: a valid visa permits
  the holder to request admission at a U.S. port of entry; it does not
  guarantee admission or determine authorized stay, and must never be
  treated as the expiration of authorized stay.
- EAD (EmploymentAuthorization) end dates are always fixed and do produce a
  countdown.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from app.countdown import (
    authorized_stay_countdown_days,
    employment_authorization_countdown_days,
    visa_validity_countdown_days,
)
from app.schemas import (
    DemoUser,
    EmploymentAuthorization,
    EmploymentAuthorizationType,
    EvidenceItem,
    ImmigrationDocument,
    ImmigrationStatus,
    ImmigrationStatusType,
    O1Criterion,
    TimelineEvent,
    VisaStamp,
)

DEMO_PROFILE_PATH = Path(__file__).resolve().parents[2] / "sample_documents" / "demo_profile.json"
DEMO_REFERENCE_DATE = date(2026, 8, 15)


@pytest.fixture(scope="module")
def demo_profile() -> dict:
    with DEMO_PROFILE_PATH.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def statuses(demo_profile: dict) -> list[ImmigrationStatus]:
    return [ImmigrationStatus(**s) for s in demo_profile["immigration_statuses"]]


@pytest.fixture(scope="module")
def employment_authorizations(demo_profile: dict) -> list[EmploymentAuthorization]:
    return [EmploymentAuthorization(**e) for e in demo_profile["employment_authorizations"]]


@pytest.fixture(scope="module")
def visa_stamps(demo_profile: dict) -> list[VisaStamp]:
    return [VisaStamp(**v) for v in demo_profile["visa_stamps"]]


@pytest.fixture(scope="module")
def events(demo_profile: dict) -> list[TimelineEvent]:
    return [TimelineEvent(**t) for t in demo_profile["timeline_events"]]


def test_demo_profile_matches_schemas(demo_profile: dict):
    DemoUser(**demo_profile["user"])
    for doc in demo_profile["documents"]:
        ImmigrationDocument(**doc)
    for status in demo_profile["immigration_statuses"]:
        ImmigrationStatus(**status)
    for auth in demo_profile["employment_authorizations"]:
        EmploymentAuthorization(**auth)
    for visa in demo_profile["visa_stamps"]:
        VisaStamp(**visa)
    for event in demo_profile["timeline_events"]:
        TimelineEvent(**event)
    for criterion in demo_profile["o1_criteria"]:
        O1Criterion(**criterion)
    for item in demo_profile["evidence_items"]:
        EvidenceItem(**item)


# (a) F-1 remains the current classification during STEM OPT.
def test_f1_remains_current_classification_during_stem_opt(
    statuses: list[ImmigrationStatus], employment_authorizations: list[EmploymentAuthorization]
):
    f1_statuses = [s for s in statuses if s.status_type == ImmigrationStatusType.F1]
    assert len(f1_statuses) == 1
    f1 = f1_statuses[0]
    assert f1.is_current is True
    assert f1.duration_of_status is True
    assert f1.end_date is None

    stem_opt = next(
        a for a in employment_authorizations if a.authorization_type == EmploymentAuthorizationType.STEM_OPT_EXTENSION
    )
    assert stem_opt.is_current is True

    # Both are current at the same time: STEM OPT is held *under* F-1, not instead of it.
    assert f1.is_current and stem_opt.is_current


# (b) OPT/STEM OPT are employment-authorization periods, not immigration statuses.
def test_opt_and_stem_opt_are_employment_authorization_periods(
    statuses: list[ImmigrationStatus], employment_authorizations: list[EmploymentAuthorization]
):
    status_types = {s.status_type for s in statuses}
    assert status_types == {ImmigrationStatusType.F1}

    auth_types = {a.authorization_type for a in employment_authorizations}
    assert auth_types == {
        EmploymentAuthorizationType.POST_COMPLETION_OPT,
        EmploymentAuthorizationType.STEM_OPT_EXTENSION,
    }

    opt = next(a for a in employment_authorizations if a.authorization_type == EmploymentAuthorizationType.POST_COMPLETION_OPT)
    stem_opt = next(
        a for a in employment_authorizations if a.authorization_type == EmploymentAuthorizationType.STEM_OPT_EXTENSION
    )
    assert opt.start_date == date(2024, 7, 1)
    assert opt.end_date == date(2025, 6, 30)
    assert stem_opt.start_date == date(2025, 7, 1)
    assert stem_opt.end_date == date(2027, 6, 30)
    assert stem_opt.start_date > opt.end_date  # no overlap


# (c) D/S does not generate a numerical status countdown.
def test_duration_of_status_produces_no_countdown(statuses: list[ImmigrationStatus]):
    f1 = next(s for s in statuses if s.status_type == ImmigrationStatusType.F1)
    assert authorized_stay_countdown_days(f1, DEMO_REFERENCE_DATE) is None


# (d) Visa-stamp expiration is not treated as authorized-stay expiration.
def test_visa_stamp_expiration_is_not_authorized_stay_expiration(
    statuses: list[ImmigrationStatus], visa_stamps: list[VisaStamp], events: list[TimelineEvent]
):
    f1 = next(s for s in statuses if s.status_type == ImmigrationStatusType.F1)
    visa = visa_stamps[0]

    # Days until the visa stamp expires is a concrete number...
    visa_countdown = visa_validity_countdown_days(visa, DEMO_REFERENCE_DATE)
    assert isinstance(visa_countdown, int)

    # ...while authorized stay (D/S) still yields no countdown at all — the two
    # are computed independently and neither substitutes for the other.
    assert authorized_stay_countdown_days(f1, DEMO_REFERENCE_DATE) is None

    visa_event = next(e for e in events if e.related_document_ids == ["doc_visa_001"])
    assert visa_event.is_deadline is False
    description = (visa_event.description or "").lower()
    assert "does not affect" in description


# (e) EAD expiration can generate a countdown.
def test_ead_expiration_generates_countdown(employment_authorizations: list[EmploymentAuthorization]):
    stem_opt = next(
        a for a in employment_authorizations if a.authorization_type == EmploymentAuthorizationType.STEM_OPT_EXTENSION
    )
    countdown = employment_authorization_countdown_days(stem_opt, DEMO_REFERENCE_DATE)
    assert isinstance(countdown, int)
    assert countdown > 0
    assert stem_opt.end_date == date(2027, 6, 30)


def test_timeline_has_upcoming_events_within_30_90_and_365_days(events: list[TimelineEvent]):
    future_days_out = sorted(
        (event.event_date - DEMO_REFERENCE_DATE).days
        for event in events
        if event.event_date > DEMO_REFERENCE_DATE
    )

    bands = [(0, 30), (30, 90), (90, 365)]
    for lower, upper in bands:
        assert any(lower < days <= upper for days in future_days_out), (
            f"expected at least one upcoming timeline event within ({lower}, {upper}] days "
            f"of {DEMO_REFERENCE_DATE.isoformat()}, found: {future_days_out}"
        )


def test_i20_program_dates_are_ordered(demo_profile: dict):
    i20_doc = next(d for d in demo_profile["documents"] if d["id"] == "doc_i20_001")
    facts = {f["label"]: f["value"] for f in i20_doc["extracted_facts"]}

    program_start = date.fromisoformat(facts["Program Start Date"])
    program_end = date.fromisoformat(facts["Program End Date"])

    assert program_start < program_end


def test_i94_entry_precedes_program_start(demo_profile: dict):
    i94_doc = next(d for d in demo_profile["documents"] if d["id"] == "doc_i94_001")
    i20_doc = next(d for d in demo_profile["documents"] if d["id"] == "doc_i20_001")

    entry_date = date.fromisoformat(
        next(f for f in i94_doc["extracted_facts"] if f["label"] == "Most Recent Date of Entry")["value"]
    )
    program_start = date.fromisoformat(
        next(f for f in i20_doc["extracted_facts"] if f["label"] == "Program Start Date")["value"]
    )

    assert entry_date <= program_start


def test_i20_program_dates_are_independent_of_status_and_ead_dates(demo_profile: dict):
    """I-20 program dates must not be reused as immigration-status or EAD dates."""
    i20_doc = next(d for d in demo_profile["documents"] if d["id"] == "doc_i20_001")
    facts = {f["label"]: f["value"] for f in i20_doc["extracted_facts"]}
    program_start = facts["Program Start Date"]
    program_end = facts["Program End Date"]

    status = next(ImmigrationStatus(**s) for s in demo_profile["immigration_statuses"])
    assert str(status.start_date) != program_start

    for auth in demo_profile["employment_authorizations"]:
        assert auth["start_date"] not in (program_start, program_end)
        assert auth["end_date"] not in (program_start, program_end)
