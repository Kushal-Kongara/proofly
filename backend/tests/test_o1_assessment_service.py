"""Deterministic O-1A assessment builder tests (Phase 4). No Featherless or
Supermemory call is ever made here — `build_o1_assessment` is pure Python
over an already-validated `O1LLMAnalysisOutput`.
"""

from datetime import date

from app.data.o1_criteria import O1_CRITERIA
from app.schemas.common import O1CriterionCode
from app.schemas.o1_assessment import (
    O1CriterionNoteDraft,
    O1CriterionStatus,
    O1EvidenceItemDraft,
    O1EvidenceRole,
    O1LLMAnalysisOutput,
)
from app.services.o1_assessment import build_o1_assessment
from app.services.reference_humanizer import SAFE_FALLBACK_LABEL

AS_OF = date(2026, 8, 15)


def _draft(**overrides) -> O1EvidenceItemDraft:
    base = dict(
        title="Evidence",
        factual_summary="A fact from a document.",
        criterion_id=O1CriterionCode.AWARDS,
        source_document_id="doc1",
        source_filename="doc1.pdf",
        confidence=0.9,
        evidence_role=O1EvidenceRole.DIRECT_DOCUMENT,
    )
    base.update(overrides)
    return O1EvidenceItemDraft(**base)


def test_all_eight_criteria_always_returned_even_with_no_evidence():
    assessment = build_o1_assessment(O1LLMAnalysisOutput(), AS_OF)

    assert len(assessment.criteria) == 8
    assert {c.definition.code for c in assessment.criteria} == set(O1CriterionCode)
    assert all(c.status == O1CriterionStatus.NO_SUPPORT_FOUND for c in assessment.criteria)
    assert assessment.summary.criteria_without_support_count == 8
    assert assessment.summary.criteria_with_document_support_count == 0


def test_criterion_definitions_come_from_static_data_not_model_output():
    assessment = build_o1_assessment(O1LLMAnalysisOutput(), AS_OF)

    definitions_by_code = {c.definition.code: c.definition for c in assessment.criteria}
    for static in O1_CRITERIA:
        assert definitions_by_code[static.code].name == static.name
        assert definitions_by_code[static.code].regulatory_description == static.regulatory_description


def test_award_without_recognition_evidence_remains_partial():
    output = O1LLMAnalysisOutput(
        evidence_items=[
            _draft(
                title="Best Emerging Researcher Award",
                criterion_id=O1CriterionCode.AWARDS,
                limitations=["Does not establish national or international recognition of the award."],
            )
        ]
    )
    assessment = build_o1_assessment(output, AS_OF)

    awards = next(c for c in assessment.criteria if c.definition.code == O1CriterionCode.AWARDS)
    assert awards.status == O1CriterionStatus.PARTIAL_SUPPORT_FOUND
    assert awards.status != O1CriterionStatus.DOCUMENTED_SUPPORT_FOUND


def test_future_judging_invitation_is_not_treated_as_completed_judging():
    output = O1LLMAnalysisOutput(
        evidence_items=[
            _draft(
                title="Judging Invitation",
                criterion_id=O1CriterionCode.JUDGING,
                date=date(2026, 9, 5),  # after AS_OF
                limitations=[],
            )
        ]
    )
    assessment = build_o1_assessment(output, AS_OF)

    judging = next(c for c in assessment.criteria if c.definition.code == O1CriterionCode.JUDGING)
    assert judging.status == O1CriterionStatus.PARTIAL_SUPPORT_FOUND
    assert judging.status != O1CriterionStatus.DOCUMENTED_SUPPORT_FOUND
    assert judging.evidence_items[0].is_future_dated is True
    assert any("future" in note.lower() or "not yet" in note.lower() for note in judging.evidence_items[0].limitations)

    action = next(a for a in assessment.action_plan if a.related_criterion == O1CriterionCode.JUDGING)
    assert action.action_type.value == "request_confirmation"


def test_resume_evidence_is_classified_self_reported_and_insufficient_alone():
    output = O1LLMAnalysisOutput(
        evidence_items=[
            _draft(
                title="Resume mentions high salary",
                criterion_id=O1CriterionCode.HIGH_REMUNERATION,
                evidence_role=O1EvidenceRole.SELF_REPORTED,
            )
        ]
    )
    assessment = build_o1_assessment(output, AS_OF)

    remuneration = next(c for c in assessment.criteria if c.definition.code == O1CriterionCode.HIGH_REMUNERATION)
    assert remuneration.evidence_items[0].evidence_role == O1EvidenceRole.SELF_REPORTED
    assert remuneration.status == O1CriterionStatus.NO_SUPPORT_FOUND


def test_employment_letter_alone_does_not_establish_critical_role():
    output = O1LLMAnalysisOutput(
        evidence_items=[
            _draft(
                title="Employment Verification Letter",
                criterion_id=O1CriterionCode.CRITICAL_EMPLOYMENT,
                limitations=["Does not establish the organization's distinguished reputation."],
            )
        ]
    )
    assessment = build_o1_assessment(output, AS_OF)

    critical = next(c for c in assessment.criteria if c.definition.code == O1CriterionCode.CRITICAL_EMPLOYMENT)
    assert critical.status == O1CriterionStatus.PARTIAL_SUPPORT_FOUND
    assert critical.status != O1CriterionStatus.DOCUMENTED_SUPPORT_FOUND


def test_innovation_award_alone_does_not_establish_major_significance():
    output = O1LLMAnalysisOutput(
        evidence_items=[
            _draft(
                title="Best Emerging Researcher Award",
                criterion_id=O1CriterionCode.ORIGINAL_CONTRIBUTION,
                limitations=["No evidence of independent adoption or measurable impact."],
            )
        ]
    )
    assessment = build_o1_assessment(output, AS_OF)

    contribution = next(c for c in assessment.criteria if c.definition.code == O1CriterionCode.ORIGINAL_CONTRIBUTION)
    assert contribution.status == O1CriterionStatus.PARTIAL_SUPPORT_FOUND
    assert contribution.status != O1CriterionStatus.DOCUMENTED_SUPPORT_FOUND


def test_clean_direct_evidence_reaches_documented_support_found():
    output = O1LLMAnalysisOutput(
        evidence_items=[
            _draft(
                title="Published feature about the applicant",
                criterion_id=O1CriterionCode.PUBLISHED_MATERIAL,
                limitations=[],
            )
        ]
    )
    assessment = build_o1_assessment(output, AS_OF)

    published = next(c for c in assessment.criteria if c.definition.code == O1CriterionCode.PUBLISHED_MATERIAL)
    assert published.status == O1CriterionStatus.DOCUMENTED_SUPPORT_FOUND


def test_conflicting_evidence_flagged_by_model_becomes_needs_expert_review():
    output = O1LLMAnalysisOutput(
        evidence_items=[
            _draft(
                title="Conflicting membership claim",
                criterion_id=O1CriterionCode.MEMBERSHIP,
                flag_for_expert_review=True,
            )
        ]
    )
    assessment = build_o1_assessment(output, AS_OF)

    membership = next(c for c in assessment.criteria if c.definition.code == O1CriterionCode.MEMBERSHIP)
    assert membership.status == O1CriterionStatus.NEEDS_EXPERT_REVIEW


def test_coverage_counts_are_deterministic_and_sum_to_eight():
    output = O1LLMAnalysisOutput(
        evidence_items=[
            _draft(criterion_id=O1CriterionCode.AWARDS, limitations=["missing recognition evidence"]),
            _draft(criterion_id=O1CriterionCode.PUBLISHED_MATERIAL, limitations=[]),
            _draft(criterion_id=O1CriterionCode.MEMBERSHIP, flag_for_expert_review=True),
        ]
    )
    assessment = build_o1_assessment(output, AS_OF)
    summary = assessment.summary

    total = (
        summary.criteria_with_document_support_count
        + summary.criteria_with_partial_support_count
        + summary.criteria_without_support_count
        + summary.criteria_needing_expert_review_count
    )
    assert total == 8
    assert summary.criteria_with_document_support_count == 1
    assert summary.criteria_with_partial_support_count == 1
    assert summary.criteria_needing_expert_review_count == 1
    assert summary.criteria_without_support_count == 5


def test_one_time_achievement_and_comparable_evidence_default_false():
    output = O1LLMAnalysisOutput(
        evidence_items=[_draft(criterion_id=O1CriterionCode.AWARDS, limitations=["missing recognition evidence"])]
    )
    assessment = build_o1_assessment(output, AS_OF)

    assert assessment.summary.one_time_achievement_documented is False
    assert assessment.summary.comparable_evidence_identified is False


def test_never_inferred_one_time_achievement_from_ordinary_award():
    """Even an award marked is_one_time_major_achievement=False stays False —
    the assessment never upgrades an ordinary award on its own."""
    output = O1LLMAnalysisOutput(
        evidence_items=[
            _draft(
                criterion_id=O1CriterionCode.AWARDS,
                is_one_time_major_achievement=False,
                limitations=["missing recognition evidence"],
            )
        ]
    )
    assessment = build_o1_assessment(output, AS_OF)
    assert assessment.summary.one_time_achievement_documented is False


def test_disclaimer_text_present_and_no_forbidden_language_anywhere():
    output = O1LLMAnalysisOutput(
        evidence_items=[_draft(criterion_id=O1CriterionCode.AWARDS, limitations=["missing recognition evidence"])]
    )
    assessment = build_o1_assessment(output, AS_OF)

    assert "Document coverage is not a determination that any USCIS criterion is satisfied." in assessment.summary.disclaimer

    dump = assessment.model_dump_json()
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
        assert forbidden not in dump


def test_requires_attorney_review_always_true():
    assessment = build_o1_assessment(O1LLMAnalysisOutput(), AS_OF)
    assert all(c.requires_attorney_review is True for c in assessment.criteria)


# --- Phase 6.1: human-readable source references only ---------------------


def _output_with_document_id_leaked_into_narrative_text(
    *, source_document_id: str = "doc1", source_filename: str = "Best_Emerging_Researcher_Award.pdf"
) -> O1LLMAnalysisOutput:
    return O1LLMAnalysisOutput(
        evidence_items=[
            _draft(
                title=f"Award notice ({source_document_id})",
                factual_summary=f"Extracted from {source_document_id}, dated 2024-11-08.",
                criterion_id=O1CriterionCode.AWARDS,
                source_document_id=source_document_id,
                source_filename=source_filename,
                limitations=[f"{source_document_id} does not establish national or international recognition."],
            )
        ],
        criterion_notes=[
            O1CriterionNoteDraft(
                criterion_id=O1CriterionCode.AWARDS,
                why_documents_may_be_relevant=f"{source_document_id} references an award relevant to this criterion.",
                what_remains_unproven=f"{source_document_id} alone does not establish recognition.",
                suggested_evidence_to_collect=[f"Independent coverage citing {source_document_id}"],
            )
        ],
    )


def test_known_document_id_in_narrative_text_becomes_the_filename():
    output = _output_with_document_id_leaked_into_narrative_text()
    assessment = build_o1_assessment(output, AS_OF)
    awards = next(c for c in assessment.criteria if c.definition.code == O1CriterionCode.AWARDS)
    item = awards.evidence_items[0]

    for narrative in [
        item.title,
        item.factual_summary,
        *item.limitations,
        awards.why_documents_may_be_relevant,
        awards.what_remains_unproven,
        *awards.suggested_evidence_to_collect,
    ]:
        assert "doc1" not in narrative
        assert "Best_Emerging_Researcher_Award.pdf" in narrative


def test_structured_source_document_id_is_never_modified():
    output = _output_with_document_id_leaked_into_narrative_text()
    assessment = build_o1_assessment(output, AS_OF)
    awards = next(c for c in assessment.criteria if c.definition.code == O1CriterionCode.AWARDS)

    assert awards.evidence_items[0].source_document_id == "doc1"


def test_unrelated_narrative_text_such_as_dates_and_receipt_numbers_is_untouched():
    output = O1LLMAnalysisOutput(
        evidence_items=[
            _draft(
                factual_summary="Receipt number MSC2190012345, dated 2024-11-08, unrelated to doc42.",
                source_document_id="doc1",
                source_filename="Award.pdf",
            )
        ]
    )
    assessment = build_o1_assessment(output, AS_OF)
    awards = next(c for c in assessment.criteria if c.definition.code == O1CriterionCode.AWARDS)

    # "doc42" was never a supplied document ID for this analysis, so it is
    # left exactly as written — only exact, known IDs are ever replaced.
    assert awards.evidence_items[0].factual_summary == (
        "Receipt number MSC2190012345, dated 2024-11-08, unrelated to doc42."
    )


def test_s1_style_id_does_not_accidentally_modify_s10():
    output = O1LLMAnalysisOutput(
        evidence_items=[
            _draft(
                title="Evidence S1",
                factual_summary="Referenced in S1 and S10.",
                criterion_id=O1CriterionCode.AWARDS,
                source_document_id="S1",
                source_filename="Award.pdf",
            ),
            _draft(
                title="Evidence S10",
                factual_summary="Referenced in S1 and S10.",
                criterion_id=O1CriterionCode.MEMBERSHIP,
                source_document_id="S10",
                source_filename="Membership.pdf",
            ),
        ]
    )
    assessment = build_o1_assessment(output, AS_OF)
    awards = next(c for c in assessment.criteria if c.definition.code == O1CriterionCode.AWARDS)
    membership = next(c for c in assessment.criteria if c.definition.code == O1CriterionCode.MEMBERSHIP)

    assert awards.evidence_items[0].factual_summary == "Referenced in Award.pdf and Membership.pdf."
    assert membership.evidence_items[0].factual_summary == "Referenced in Award.pdf and Membership.pdf."


def test_missing_source_filename_falls_back_to_safe_label():
    output = O1LLMAnalysisOutput(
        evidence_items=[
            _draft(
                title="Reference doc1 for context.",
                source_document_id="doc1",
                source_filename="",
            )
        ]
    )
    assessment = build_o1_assessment(output, AS_OF)
    awards = next(c for c in assessment.criteria if c.definition.code == O1CriterionCode.AWARDS)

    assert awards.evidence_items[0].title == f"Reference {SAFE_FALLBACK_LABEL} for context."
    assert "doc1" not in awards.evidence_items[0].title


def test_status_calculation_unaffected_by_narrative_humanization():
    output = _output_with_document_id_leaked_into_narrative_text()
    assessment = build_o1_assessment(output, AS_OF)
    awards = next(c for c in assessment.criteria if c.definition.code == O1CriterionCode.AWARDS)

    # Same status as the equivalent evidence in
    # test_award_without_recognition_evidence_remains_partial — humanizing
    # the narrative text must never change the deterministic status.
    assert awards.status == O1CriterionStatus.PARTIAL_SUPPORT_FOUND


def test_unmapped_criterion_note_for_criterion_without_evidence_is_ignored_safely():
    """A criterion_notes entry references a criterion with zero evidence items —
    it should still be usable for the text fields without crashing or fabricating evidence."""
    from app.schemas.o1_assessment import O1CriterionNoteDraft

    output = O1LLMAnalysisOutput(
        criterion_notes=[
            O1CriterionNoteDraft(
                criterion_id=O1CriterionCode.SCHOLARLY_ARTICLES,
                why_documents_may_be_relevant="No documents reference scholarly authorship.",
                what_remains_unproven="Everything — no evidence has been collected yet.",
                suggested_evidence_to_collect=["Published scholarly articles"],
            )
        ]
    )
    assessment = build_o1_assessment(output, AS_OF)
    scholarly = next(c for c in assessment.criteria if c.definition.code == O1CriterionCode.SCHOLARLY_ARTICLES)
    assert scholarly.status == O1CriterionStatus.NO_SUPPORT_FOUND
    assert scholarly.evidence_items == []
    assert scholarly.suggested_evidence_to_collect == ["Published scholarly articles"]
