"""Deterministic O-1A evidence-readiness assessment builder (Phase 4).

Turns a validated `O1LLMAnalysisOutput` (Featherless's raw, document-grounded
evidence facts) into a full `O1Assessment`. Every criterion `status`, every
coverage count, `documentation_coverage`, the highest-priority gaps, and the
action plan are computed here in plain Python — the model is never asked
for, and this module never trusts, a status, a count, or a legal
conclusion. See `docs/ARCHITECTURE.md` and `docs/PRODUCT_SPEC.md`.

Status-derivation rule (deterministic, from `evidence_role`/`limitations`/
`is_future_dated`/`flag_for_expert_review` only — never free-text parsing
of the model's prose):

- No evidence items for a criterion -> `no_support_found`.
- Any item flagged `flag_for_expert_review` -> `needs_expert_review`.
- Only `self_reported` items (e.g. a resume) -> `no_support_found`: a
  self-reported fact is a lead, never independent proof on its own.
- At least one `direct_document`/`supporting_document` item that is not
  future-dated and carries no limitation -> `documented_support_found`.
- Otherwise (evidence exists but is future-dated and/or carries a
  limitation) -> `partial_support_found`.

This directly encodes the required reasoning rules: an award certificate
with a "missing recognition evidence" limitation stays partial; a judging
invitation dated after `as_of_date` is always at most partial (never
completed judging); an employment letter alone (limitation: reputation/
criticality not established) stays partial; an innovation award alone
(limitation: no independent-impact evidence) stays partial.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date

from app.data.o1_criteria import O1_CRITERIA, O1_DEFAULT_SUGGESTED_EVIDENCE, O1_OFFICIAL_SOURCES
from app.schemas.common import O1CriterionCode
from app.schemas.o1_assessment import (
    O1ActionItem,
    O1ActionPriority,
    O1ActionType,
    O1Assessment,
    O1AssessmentSummary,
    O1CriterionAssessment,
    O1CriterionNoteDraft,
    O1CriterionStatus,
    O1DocumentationCoverage,
    O1EvidenceItem,
    O1EvidenceItemDraft,
    O1EvidenceRole,
    O1Gap,
    O1LLMAnalysisOutput,
)
from app.services.reference_humanizer import SAFE_FALLBACK_LABEL, humanize_references

DOCUMENT_COVERAGE_DISCLAIMER = (
    "Document coverage is not a determination that any USCIS criterion is satisfied."
)

FULL_DISCLAIMER = (
    f"{DOCUMENT_COVERAGE_DISCLAIMER} Proofly evaluates document readiness, not visa "
    "eligibility. An attorney must evaluate the complete case."
)

_PRIORITY_ORDER = {O1ActionPriority.HIGH: 0, O1ActionPriority.MEDIUM: 1, O1ActionPriority.LOW: 2}
_MAX_HIGHEST_PRIORITY_GAPS = 5


def _materialize_evidence_item(draft: O1EvidenceItemDraft, *, as_of_date: date) -> O1EvidenceItem:
    is_future = draft.date is not None and draft.date > as_of_date
    limitations = list(draft.limitations)
    if is_future and not any("future" in note.lower() or "not yet" in note.lower() for note in limitations):
        limitations.append(
            "This document describes a planned/future event as of the analysis date — it is "
            "not proof of a completed action."
        )
    return O1EvidenceItem(
        id=f"o1ev_{uuid.uuid4().hex[:12]}",
        title=draft.title,
        factual_summary=draft.factual_summary,
        criterion_id=draft.criterion_id,
        source_document_id=draft.source_document_id,
        source_filename=draft.source_filename,
        page_number=draft.page_number,
        confidence=draft.confidence,
        evidence_role=draft.evidence_role,
        limitations=limitations,
        date=draft.date,
        is_future_dated=is_future,
        is_one_time_major_achievement=draft.is_one_time_major_achievement,
        is_comparable_evidence=draft.is_comparable_evidence,
    )


def _status_for_criterion(pairs: list[tuple[O1EvidenceItem, O1EvidenceItemDraft]]) -> O1CriterionStatus:
    if not pairs:
        return O1CriterionStatus.NO_SUPPORT_FOUND

    if any(draft.flag_for_expert_review for _, draft in pairs):
        return O1CriterionStatus.NEEDS_EXPERT_REVIEW

    non_self_reported = [item for item, _ in pairs if item.evidence_role != O1EvidenceRole.SELF_REPORTED]
    if not non_self_reported:
        return O1CriterionStatus.NO_SUPPORT_FOUND

    clean_direct = [item for item in non_self_reported if not item.is_future_dated and not item.limitations]
    if clean_direct:
        return O1CriterionStatus.DOCUMENTED_SUPPORT_FOUND

    return O1CriterionStatus.PARTIAL_SUPPORT_FOUND


def _default_why_relevant(criterion_name: str, items: list[O1EvidenceItem]) -> str:
    if items:
        return f"Analyzed documents reference information potentially relevant to {criterion_name.lower()}."
    return "No analyzed documents were identified as relevant to this criterion."


def _default_what_remains_unproven(status: O1CriterionStatus) -> str:
    if status == O1CriterionStatus.NO_SUPPORT_FOUND:
        return "No documentary evidence for this criterion has been identified yet."
    if status == O1CriterionStatus.PARTIAL_SUPPORT_FOUND:
        return (
            "The identified documents do not, on their own, fully establish this criterion — "
            "independent corroborating evidence has not been documented."
        )
    if status == O1CriterionStatus.NEEDS_EXPERT_REVIEW:
        return "The identified documents include unresolved ambiguity that requires attorney review."
    return "Document coverage exists for this criterion, but only an attorney can determine legal sufficiency."


def _criterion_assessment(
    definition,
    pairs: list[tuple[O1EvidenceItem, O1EvidenceItemDraft]],
    note: O1CriterionNoteDraft | None,
) -> O1CriterionAssessment:
    items = [item for item, _ in pairs]
    status = _status_for_criterion(pairs)

    why = note.why_documents_may_be_relevant if note else _default_why_relevant(definition.name, items)
    unproven = note.what_remains_unproven if note else _default_what_remains_unproven(status)
    suggested = (
        note.suggested_evidence_to_collect
        if note and note.suggested_evidence_to_collect
        else O1_DEFAULT_SUGGESTED_EVIDENCE.get(definition.code, [])
    )

    return O1CriterionAssessment(
        definition=definition,
        status=status,
        evidence_items=items,
        why_documents_may_be_relevant=why,
        what_remains_unproven=unproven,
        suggested_evidence_to_collect=suggested,
    )


def _humanize_evidence_item(item: O1EvidenceItem, id_to_label: dict[str, str]) -> O1EvidenceItem:
    """Replace any raw source_document_id the model wrote into its own
    narrative text (title/factual_summary/limitations) with the document's
    filename. `source_document_id` itself — the structured field — is never
    touched here.
    """
    return item.model_copy(
        update={
            "title": humanize_references(item.title, id_to_label),
            "factual_summary": humanize_references(item.factual_summary, id_to_label),
            "limitations": [humanize_references(note, id_to_label) for note in item.limitations],
        }
    )


def _humanize_criterion_assessment(
    assessment: O1CriterionAssessment, id_to_label: dict[str, str]
) -> O1CriterionAssessment:
    return assessment.model_copy(
        update={
            "evidence_items": [_humanize_evidence_item(item, id_to_label) for item in assessment.evidence_items],
            "why_documents_may_be_relevant": humanize_references(assessment.why_documents_may_be_relevant, id_to_label),
            "what_remains_unproven": humanize_references(assessment.what_remains_unproven, id_to_label),
            "suggested_evidence_to_collect": [
                humanize_references(entry, id_to_label) for entry in assessment.suggested_evidence_to_collect
            ],
        }
    )


def _documentation_coverage(documented: int, partial: int) -> O1DocumentationCoverage:
    if documented >= 5:
        return O1DocumentationCoverage.BROAD
    if documented >= 2 or (documented + partial) >= 4:
        return O1DocumentationCoverage.DEVELOPING
    return O1DocumentationCoverage.LIMITED


def _highest_priority_gaps(criteria: list[O1CriterionAssessment]) -> list[O1Gap]:
    gaps: list[O1Gap] = []
    for assessment in criteria:
        if assessment.status == O1CriterionStatus.NO_SUPPORT_FOUND:
            gaps.append(
                O1Gap(
                    criterion_id=assessment.definition.code,
                    description=f"No supporting document found for {assessment.definition.name}.",
                    priority=O1ActionPriority.HIGH,
                )
            )
        elif assessment.status == O1CriterionStatus.NEEDS_EXPERT_REVIEW:
            gaps.append(
                O1Gap(
                    criterion_id=assessment.definition.code,
                    description=(
                        f"{assessment.definition.name} evidence needs attorney review to resolve ambiguity."
                    ),
                    priority=O1ActionPriority.HIGH,
                )
            )
        elif assessment.status == O1CriterionStatus.PARTIAL_SUPPORT_FOUND:
            gaps.append(
                O1Gap(
                    criterion_id=assessment.definition.code,
                    description=(
                        f"Partial documentation only for {assessment.definition.name} — independent "
                        "corroboration has not been documented."
                    ),
                    priority=O1ActionPriority.MEDIUM,
                )
            )

    gaps.sort(key=lambda gap: _PRIORITY_ORDER[gap.priority])
    return gaps[:_MAX_HIGHEST_PRIORITY_GAPS]


def _build_action_plan(criteria: list[O1CriterionAssessment]) -> list[O1ActionItem]:
    actions: list[O1ActionItem] = []

    for assessment in criteria:
        definition = assessment.definition

        if assessment.status == O1CriterionStatus.NO_SUPPORT_FOUND:
            actions.append(
                O1ActionItem(
                    action_type=O1ActionType.COLLECT_DOCUMENT,
                    priority=O1ActionPriority.HIGH,
                    related_criterion=definition.code,
                    action=f"Identify and collect documentary evidence for {definition.name}.",
                    why_it_matters=definition.regulatory_description,
                    suggested_supporting_materials=O1_DEFAULT_SUGGESTED_EVIDENCE.get(definition.code, []),
                )
            )
        elif assessment.status == O1CriterionStatus.PARTIAL_SUPPORT_FOUND:
            has_future = any(item.is_future_dated for item in assessment.evidence_items)
            if definition.code == O1CriterionCode.JUDGING and has_future:
                actions.append(
                    O1ActionItem(
                        action_type=O1ActionType.REQUEST_CONFIRMATION,
                        priority=O1ActionPriority.MEDIUM,
                        related_criterion=definition.code,
                        action="After the planned judging event takes place, obtain confirmation and completed records.",
                        why_it_matters=(
                            "An invitation documents a planned role, not completed judging experience."
                        ),
                        suggested_supporting_materials=[
                            "Organizer confirmation of participation",
                            "Completed scorecards with sensitive information removed",
                            "Event program or records listing the judging role",
                        ],
                    )
                )
            else:
                actions.append(
                    O1ActionItem(
                        action_type=O1ActionType.OBTAIN_INDEPENDENT_EVIDENCE,
                        priority=O1ActionPriority.MEDIUM,
                        related_criterion=definition.code,
                        action=f"Strengthen the existing {definition.name} evidence with independent corroboration.",
                        why_it_matters=assessment.what_remains_unproven,
                        suggested_supporting_materials=O1_DEFAULT_SUGGESTED_EVIDENCE.get(definition.code, []),
                    )
                )
        elif assessment.status == O1CriterionStatus.NEEDS_EXPERT_REVIEW:
            actions.append(
                O1ActionItem(
                    action_type=O1ActionType.ATTORNEY_REVIEW,
                    priority=O1ActionPriority.HIGH,
                    related_criterion=definition.code,
                    action=f"Have an immigration attorney resolve the ambiguity in the {definition.name} evidence.",
                    why_it_matters="Automated analysis cannot resolve conflicting or ambiguous evidence.",
                )
            )
        elif assessment.status == O1CriterionStatus.DOCUMENTED_SUPPORT_FOUND:
            actions.append(
                O1ActionItem(
                    action_type=O1ActionType.VERIFY_FACT,
                    priority=O1ActionPriority.LOW,
                    related_criterion=definition.code,
                    action=f"Verify and finalize the {definition.name} documentation on file.",
                    why_it_matters="Confirm the extracted details are accurate and complete before attorney review.",
                )
            )

    actions.append(
        O1ActionItem(
            action_type=O1ActionType.ATTORNEY_REVIEW,
            priority=O1ActionPriority.HIGH,
            related_criterion=None,
            action="Have an immigration attorney review the complete evidence file.",
            why_it_matters=(
                "Proofly organizes evidence and highlights gaps; it does not determine legal "
                "sufficiency for any O-1A criterion."
            ),
        )
    )

    actions.sort(key=lambda action: _PRIORITY_ORDER[action.priority])
    return actions


def build_o1_assessment(llm_output: O1LLMAnalysisOutput, as_of_date: date) -> O1Assessment:
    """The only place an `O1Assessment` is constructed. Always emits all
    eight static criteria (`O1_CRITERIA`), regardless of what the model
    returned, and computes every status/count/coverage label in Python.
    """
    materialized = [
        (_materialize_evidence_item(draft, as_of_date=as_of_date), draft) for draft in llm_output.evidence_items
    ]
    notes_by_criterion = {note.criterion_id: note for note in llm_output.criterion_notes}

    pairs_by_criterion: dict[O1CriterionCode, list[tuple[O1EvidenceItem, O1EvidenceItemDraft]]] = {
        c.code: [] for c in O1_CRITERIA
    }
    for item, draft in materialized:
        if draft.criterion_id in pairs_by_criterion:
            pairs_by_criterion[draft.criterion_id].append((item, draft))

    criteria = [
        _criterion_assessment(definition, pairs_by_criterion[definition.code], notes_by_criterion.get(definition.code))
        for definition in O1_CRITERIA
    ]

    # Deterministic backend-boundary enforcement: never let a raw Supermemory
    # document ID reach user-facing narrative text, even if the model wrote
    # one directly into a summary/limitation/note despite the prompt
    # instruction above. Built only from IDs actually supplied for this
    # analysis (source_document_id is always one of them — enforced by
    # O1LLMAnalysisOutput's citation-membership validator), so this never
    # touches unrelated text such as dates or receipt numbers.
    id_to_label = {
        item.source_document_id: (item.source_filename or SAFE_FALLBACK_LABEL) for item, _ in materialized
    }
    criteria = [_humanize_criterion_assessment(assessment, id_to_label) for assessment in criteria]

    counts = Counter(assessment.status for assessment in criteria)
    documented = counts[O1CriterionStatus.DOCUMENTED_SUPPORT_FOUND]
    partial = counts[O1CriterionStatus.PARTIAL_SUPPORT_FOUND]
    none_found = counts[O1CriterionStatus.NO_SUPPORT_FOUND]
    needs_review = counts[O1CriterionStatus.NEEDS_EXPERT_REVIEW]

    one_time_achievement_documented = any(item.is_one_time_major_achievement for item, _ in materialized)
    comparable_evidence_identified = any(item.is_comparable_evidence for item, _ in materialized)

    summary = O1AssessmentSummary(
        criteria_with_document_support_count=documented,
        criteria_with_partial_support_count=partial,
        criteria_without_support_count=none_found,
        criteria_needing_expert_review_count=needs_review,
        one_time_achievement_documented=one_time_achievement_documented,
        comparable_evidence_identified=comparable_evidence_identified,
        documentation_coverage=_documentation_coverage(documented, partial),
        highest_priority_gaps=_highest_priority_gaps(criteria),
        disclaimer=FULL_DISCLAIMER,
        official_sources=O1_OFFICIAL_SOURCES,
    )

    return O1Assessment(
        criteria=criteria,
        summary=summary,
        action_plan=_build_action_plan(criteria),
        as_of_date=as_of_date,
    )
