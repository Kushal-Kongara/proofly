"""Deterministic timeline unit tests — pure Python, no mocking needed."""

from datetime import date, timedelta

from app.schemas.analysis import (
    AcademicProgramRecord,
    EmploymentAuthorizationRecord,
    EmploymentAuthorizationType,
    I94AdmitUntil,
    I94AdmitUntilType,
    ImmigrationStatusType,
    LLMAnalysisOutput,
    PassportRecord,
    ReportedImmigrationClassification,
    TimelineEventCategory,
    TimelineEventDisplayStatus,
    VisaStampRecord,
)
from app.services.timeline import _status_for_days, build_timeline

AS_OF = date(2026, 8, 15)


def test_d_s_produces_no_numerical_countdown():
    result = LLMAnalysisOutput(
        reported_classification=ReportedImmigrationClassification(
            classification=ImmigrationStatusType.F1,
            admit_until=I94AdmitUntil(type=I94AdmitUntilType.DURATION_OF_STATUS, raw_value="D/S"),
            source_document_id="doc1",
            source_filename="i94.pdf",
            confidence=0.95,
        )
    )

    events = build_timeline(result, AS_OF)

    status_events = [e for e in events if e.category == TimelineEventCategory.STATUS]
    assert len(status_events) == 1
    event = status_events[0]
    assert event.event_date is None
    assert event.days_remaining is None
    assert event.status == TimelineEventDisplayStatus.INFORMATIONAL
    assert event.affects_authorized_stay is None
    assert "D/S" in event.explanation


def test_fixed_admission_date_does_produce_a_countdown():
    result = LLMAnalysisOutput(
        reported_classification=ReportedImmigrationClassification(
            classification=ImmigrationStatusType.H1B,
            admit_until=I94AdmitUntil(
                type=I94AdmitUntilType.FIXED_DATE, raw_value="06/30/2028", admit_until_date=date(2028, 6, 30)
            ),
            source_document_id="doc1",
            source_filename="i94.pdf",
            confidence=0.9,
        )
    )

    events = build_timeline(result, AS_OF)

    status_events = [e for e in events if e.category == TimelineEventCategory.STATUS]
    assert len(status_events) == 1
    event = status_events[0]
    assert event.event_date == date(2028, 6, 30)
    assert event.days_remaining == (date(2028, 6, 30) - AS_OF).days
    assert event.affects_authorized_stay is True


def test_ead_expiration_produces_countdown_and_is_labeled_work_authorization():
    result = LLMAnalysisOutput(
        employment_authorizations=[
            EmploymentAuthorizationRecord(
                authorization_type=EmploymentAuthorizationType.STEM_OPT_EXTENSION,
                start_date=date(2025, 7, 1),
                end_date=date(2027, 6, 30),
                source_document_id="doc_ead",
                source_filename="ead.pdf",
                page_number=1,
                confidence=0.96,
            )
        ]
    )

    events = build_timeline(result, AS_OF)

    assert len(events) == 1
    event = events[0]
    assert event.category == TimelineEventCategory.WORK_AUTHORIZATION
    assert event.event_date == date(2027, 6, 30)
    assert event.days_remaining == (date(2027, 6, 30) - AS_OF).days
    assert "work authorization" in event.title.lower()
    # Work-authorization expiration is never automatically true or false —
    # only visa-stamp expiration is deterministically False.
    assert event.affects_authorized_stay is None
    assert event.source.document_id == "doc_ead"
    assert event.source.page_number == 1


def test_past_opt_ead_period_is_historical_not_overdue():
    result = LLMAnalysisOutput(
        employment_authorizations=[
            EmploymentAuthorizationRecord(
                authorization_type=EmploymentAuthorizationType.POST_COMPLETION_OPT,
                start_date=date(2024, 7, 1),
                end_date=date(2025, 6, 30),
                source_document_id="doc_ead",
                source_filename="ead.pdf",
                confidence=0.97,
            )
        ]
    )

    events = build_timeline(result, AS_OF)

    assert len(events) == 1
    assert events[0].status == TimelineEventDisplayStatus.HISTORICAL
    assert events[0].status != TimelineEventDisplayStatus.OVERDUE
    assert events[0].affects_authorized_stay is None


def test_ead_with_no_end_date_produces_no_event():
    result = LLMAnalysisOutput(
        employment_authorizations=[
            EmploymentAuthorizationRecord(
                authorization_type=EmploymentAuthorizationType.POST_COMPLETION_OPT,
                start_date=date(2024, 7, 1),
                end_date=None,
                source_document_id="doc_ead",
                source_filename="ead.pdf",
                confidence=0.5,
            )
        ]
    )

    events = build_timeline(result, AS_OF)

    assert events == []


def test_visa_expiration_never_sets_affects_authorized_stay_true():
    result = LLMAnalysisOutput(
        visa_stamps=[
            VisaStampRecord(
                visa_class="F-1",
                issue_date=date(2022, 7, 10),
                expiration_date=date(2027, 7, 9),
                source_document_id="doc_visa",
                source_filename="visa.pdf",
                confidence=0.9,
            )
        ]
    )

    events = build_timeline(result, AS_OF)

    assert len(events) == 1
    event = events[0]
    assert event.category == TimelineEventCategory.VISA_VALIDITY
    # Visa expiration is the ONLY event type deterministically marked False.
    assert event.affects_authorized_stay is False
    assert "visa validity" in event.title.lower() or "visa" in event.title.lower()
    assert "status" not in event.title.lower()
    assert "authorized stay" not in event.title.lower()


def test_i20_program_end_is_not_automatically_f1_expiration():
    result = LLMAnalysisOutput(
        academic_program=AcademicProgramRecord(
            school_name="Northbridge University",
            program_name="M.S. Computer Science",
            program_start_date=date(2022, 8, 22),
            program_end_date=date(2024, 5, 18),
            source_document_id="doc_i20",
            source_filename="i20.pdf",
            confidence=0.96,
        )
    )

    events = build_timeline(result, AS_OF)

    assert len(events) == 1
    event = events[0]
    assert event.category == TimelineEventCategory.ACADEMIC_PROGRAM
    # Explicitly unknown, not False and not True — the rule is "not automatically labeled."
    assert event.affects_authorized_stay is None
    assert "f-1" not in event.title.lower()
    assert "status" not in event.title.lower()


def test_past_i20_program_end_is_historical_not_overdue():
    # AS_OF (2026-08-15) is well after this program end date — a plain past
    # academic fact, not a missed legal deadline.
    result = LLMAnalysisOutput(
        academic_program=AcademicProgramRecord(
            school_name="Northbridge University",
            program_name="M.S. Computer Science",
            program_start_date=date(2022, 8, 22),
            program_end_date=date(2024, 5, 18),
            source_document_id="doc_i20",
            source_filename="i20.pdf",
            confidence=0.96,
        )
    )

    events = build_timeline(result, AS_OF)

    assert len(events) == 1
    assert events[0].status == TimelineEventDisplayStatus.HISTORICAL
    assert events[0].status != TimelineEventDisplayStatus.OVERDUE


def test_passport_expiration_event_when_present():
    result = LLMAnalysisOutput(
        passport=PassportRecord(
            expiration_date=date(2029, 1, 1),
            source_document_id="doc_passport",
            source_filename="passport.pdf",
            confidence=0.9,
        )
    )

    events = build_timeline(result, AS_OF)

    assert len(events) == 1
    assert events[0].category == TimelineEventCategory.PASSPORT
    assert events[0].affects_authorized_stay is None


def test_status_thresholds_urgent_historical_upcoming():
    def _auth(end_date: date) -> EmploymentAuthorizationRecord:
        return EmploymentAuthorizationRecord(
            authorization_type=EmploymentAuthorizationType.POST_COMPLETION_OPT,
            end_date=end_date,
            source_document_id="doc1",
            source_filename="ead.pdf",
            confidence=0.9,
        )

    past = build_timeline(LLMAnalysisOutput(employment_authorizations=[_auth(AS_OF - timedelta(days=1))]), AS_OF)[0]
    urgent = build_timeline(LLMAnalysisOutput(employment_authorizations=[_auth(AS_OF + timedelta(days=10))]), AS_OF)[0]
    upcoming = build_timeline(LLMAnalysisOutput(employment_authorizations=[_auth(AS_OF + timedelta(days=200))]), AS_OF)[0]

    # A past date with no explicit missed deadline is historical, never overdue.
    assert past.status == TimelineEventDisplayStatus.HISTORICAL
    assert urgent.status == TimelineEventDisplayStatus.URGENT
    assert upcoming.status == TimelineEventDisplayStatus.UPCOMING


def test_no_current_synthetic_event_builder_ever_marks_overdue():
    """None of Proofly's current timeline sources represent an explicit
    missed deadline, so `build_timeline` must never emit `overdue` — past
    dates always come out `historical` instead.
    """
    result = LLMAnalysisOutput(
        employment_authorizations=[
            EmploymentAuthorizationRecord(
                authorization_type=EmploymentAuthorizationType.POST_COMPLETION_OPT,
                end_date=date(2020, 1, 1),
                source_document_id="doc1",
                source_filename="ead.pdf",
                confidence=0.9,
            )
        ],
        visa_stamps=[
            VisaStampRecord(
                expiration_date=date(2020, 1, 1),
                source_document_id="doc2",
                source_filename="visa.pdf",
                confidence=0.9,
            )
        ],
        passport=PassportRecord(
            expiration_date=date(2020, 1, 1),
            source_document_id="doc3",
            source_filename="passport.pdf",
            confidence=0.9,
        ),
        academic_program=AcademicProgramRecord(
            program_end_date=date(2020, 1, 1),
            source_document_id="doc4",
            source_filename="i20.pdf",
            confidence=0.9,
        ),
        reported_classification=ReportedImmigrationClassification(
            classification=ImmigrationStatusType.H1B,
            admit_until=I94AdmitUntil(
                type=I94AdmitUntilType.FIXED_DATE, raw_value="01/01/2020", admit_until_date=date(2020, 1, 1)
            ),
            source_document_id="doc5",
            source_filename="i94.pdf",
            confidence=0.9,
        ),
    )

    events = build_timeline(result, AS_OF)

    assert len(events) == 5
    assert all(event.status != TimelineEventDisplayStatus.OVERDUE for event in events)
    assert all(event.status == TimelineEventDisplayStatus.HISTORICAL for event in events)


def test_status_for_days_can_still_produce_overdue_for_an_explicit_deadline():
    """The mechanism exists for a future explicit-deadline source — it's
    just never invoked with is_required_deadline=True today.
    """
    assert _status_for_days(-1, is_required_deadline=True) == TimelineEventDisplayStatus.OVERDUE
    assert _status_for_days(-1, is_required_deadline=False) == TimelineEventDisplayStatus.HISTORICAL


def test_no_source_documents_no_events():
    assert build_timeline(LLMAnalysisOutput(), AS_OF) == []
