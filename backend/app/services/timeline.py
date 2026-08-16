"""Deterministic timeline computation.

Timeline events are always built here, in plain Python, from already
Pydantic-validated extracted dates — the LLM is never asked to compute
days-remaining, urgency, or legal deadlines. This keeps every date and
every "how many days left" number auditable and reproducible without a
model call, and keeps the legal-effect labeling rules (D/S vs fixed date,
visa vs status, EAD vs status, I-20 vs status) enforced in one place.
"""

from __future__ import annotations

from datetime import date

from app.schemas.analysis import (
    EmploymentAuthorizationType,
    I94AdmitUntilType,
    ImmigrationStatusType,
    LLMAnalysisOutput,
    TimelineAnalysisEvent,
    TimelineEventCategory,
    TimelineEventDisplayStatus,
)
from app.schemas.source_citation import SourceCitation

_AUTH_LABELS: dict[EmploymentAuthorizationType, str] = {
    EmploymentAuthorizationType.POST_COMPLETION_OPT: "Post-completion OPT",
    EmploymentAuthorizationType.STEM_OPT_EXTENSION: "STEM OPT extension",
    EmploymentAuthorizationType.OTHER: "Employment authorization",
}

_CLASSIFICATION_LABELS: dict[ImmigrationStatusType, str] = {
    ImmigrationStatusType.F1: "F-1",
    ImmigrationStatusType.H1B: "H-1B",
    ImmigrationStatusType.O1A: "O-1A",
    ImmigrationStatusType.OTHER: "reported",
}


def _status_for_days(days_remaining: int, *, is_required_deadline: bool = False) -> TimelineEventDisplayStatus:
    """`overdue` is reserved for a source *explicitly* identifying a required
    action or deadline that has been missed — none of the dates Proofly
    extracts today are that (an EAD end date, an I-20 program end date, a
    visa/passport expiration, or a reported admission end date are all just
    facts printed on a document, not "you must act by this date"
    statements). A past date without an explicit missed deadline is
    `historical`, never `overdue`.
    """
    if days_remaining < 0:
        return TimelineEventDisplayStatus.OVERDUE if is_required_deadline else TimelineEventDisplayStatus.HISTORICAL
    if days_remaining <= 30:
        return TimelineEventDisplayStatus.URGENT
    return TimelineEventDisplayStatus.UPCOMING


def build_timeline(result: LLMAnalysisOutput, as_of_date: date) -> list[TimelineAnalysisEvent]:
    events: list[TimelineAnalysisEvent] = []

    for auth in result.employment_authorizations:
        if auth.end_date is None:
            continue  # never invent a missing date
        days = (auth.end_date - as_of_date).days
        events.append(
            TimelineAnalysisEvent(
                title=f"{_AUTH_LABELS[auth.authorization_type]} work authorization expires",
                event_date=auth.end_date,
                category=TimelineEventCategory.WORK_AUTHORIZATION,
                days_remaining=days,
                status=_status_for_days(days),
                source=SourceCitation(document_id=auth.source_document_id, page_number=auth.page_number),
                explanation=(
                    "Employment authorization (EAD) end date as reported in the source document. "
                    "This is a work-authorization date, not a status determination."
                ),
                affects_authorized_stay=None,
                requires_user_verification=True,
            )
        )

    for visa in result.visa_stamps:
        if visa.expiration_date is None:
            continue
        days = (visa.expiration_date - as_of_date).days
        events.append(
            TimelineAnalysisEvent(
                title="Visa stamp validity ends",
                event_date=visa.expiration_date,
                category=TimelineEventCategory.VISA_VALIDITY,
                days_remaining=days,
                status=_status_for_days(days),
                source=SourceCitation(document_id=visa.source_document_id, page_number=visa.page_number),
                explanation=(
                    "Visa stamp expiration governs eligibility to seek admission at a U.S. port of "
                    "entry only. It does not determine authorized stay in the U.S."
                ),
                # Visa expiration is the ONLY event type Proofly deterministically marks
                # affects_authorized_stay=False for — it is the one case a document type
                # alone safely proves "does not affect authorized stay." Every other
                # event type defaults to unknown (None) rather than guessing.
                affects_authorized_stay=False,
                requires_user_verification=True,
            )
        )

    if result.passport is not None:
        days = (result.passport.expiration_date - as_of_date).days
        events.append(
            TimelineAnalysisEvent(
                title="Passport expires",
                event_date=result.passport.expiration_date,
                category=TimelineEventCategory.PASSPORT,
                days_remaining=days,
                status=_status_for_days(days),
                source=SourceCitation(
                    document_id=result.passport.source_document_id, page_number=result.passport.page_number
                ),
                explanation=(
                    "Passport expiration as reported in the source document. Unrelated to F-1 status "
                    "or work authorization."
                ),
                affects_authorized_stay=None,
                requires_user_verification=True,
            )
        )

    if result.academic_program is not None and result.academic_program.program_end_date is not None:
        program = result.academic_program
        days = (program.program_end_date - as_of_date).days
        events.append(
            TimelineAnalysisEvent(
                title="Academic program end date (I-20)",
                event_date=program.program_end_date,
                category=TimelineEventCategory.ACADEMIC_PROGRAM,
                days_remaining=days,
                status=_status_for_days(days),
                source=SourceCitation(document_id=program.source_document_id, page_number=program.page_number),
                explanation=(
                    "Program end date reported on the I-20. This is an academic date — it is not "
                    "automatically the expiration of F-1 status."
                ),
                affects_authorized_stay=None,
                requires_user_verification=True,
            )
        )

    if result.reported_classification is not None:
        classification = result.reported_classification
        admit = classification.admit_until
        label = _CLASSIFICATION_LABELS[classification.classification]
        citation = SourceCitation(
            document_id=classification.source_document_id, page_number=classification.page_number
        )

        if admit.type == I94AdmitUntilType.FIXED_DATE and admit.admit_until_date is not None:
            days = (admit.admit_until_date - as_of_date).days
            events.append(
                TimelineAnalysisEvent(
                    title=f"Reported {label} admission period ends",
                    event_date=admit.admit_until_date,
                    category=TimelineEventCategory.STATUS,
                    days_remaining=days,
                    status=_status_for_days(days),
                    source=citation,
                    explanation=f"Admission end date as reported on the I-94 for {label} status.",
                    affects_authorized_stay=True,
                    requires_user_verification=True,
                )
            )
        elif admit.type == I94AdmitUntilType.DURATION_OF_STATUS:
            # D/S has no fixed end date — no countdown is computed or fabricated.
            events.append(
                TimelineAnalysisEvent(
                    title=f"{label} status: admitted for duration of status (D/S)",
                    event_date=None,
                    category=TimelineEventCategory.STATUS,
                    days_remaining=None,
                    status=TimelineEventDisplayStatus.INFORMATIONAL,
                    source=citation,
                    explanation=(
                        "I-94 shows 'D/S' (duration of status) — there is no fixed expiration date on "
                        "file, and Proofly does not calculate one."
                    ),
                    affects_authorized_stay=None,
                    requires_user_verification=True,
                )
            )
        # admit.type == UNKNOWN -> not enough information for any timeline entry

    events.sort(key=lambda event: (event.event_date is None, event.event_date or date.max))
    return events
