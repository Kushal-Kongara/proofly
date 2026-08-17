"""Unit tests for the shared deterministic reference-humanization utility
(Phase 6.1) used by both the O-1A assessment builder and the chat router.
"""

from app.services.reference_humanizer import SAFE_FALLBACK_LABEL, humanize_references


def test_known_token_is_replaced_with_its_label():
    text = "The award notice was extracted from doc_award."
    result = humanize_references(text, {"doc_award": "Innovation_Award.pdf"})
    assert result == "The award notice was extracted from Innovation_Award.pdf."
    assert "doc_award" not in result


def test_unrelated_text_is_left_untouched():
    text = "Issued November 8, 2024, receipt number MSC2190012345."
    result = humanize_references(text, {"doc_award": "Innovation_Award.pdf"})
    assert result == text


def test_short_key_does_not_match_inside_a_longer_key():
    text = "Cited in S1 and S10."
    result = humanize_references(text, {"S1": "Award.pdf", "S10": "Membership.pdf"})
    assert result == "Cited in Award.pdf and Membership.pdf."


def test_replacing_only_s1_leaves_s10_untouched():
    text = "Cited in S1 and S10."
    result = humanize_references(text, {"S1": "Award.pdf"})
    assert result == "Cited in Award.pdf and S10."


def test_empty_label_map_is_a_no_op():
    text = "Nothing to replace here."
    assert humanize_references(text, {}) == text


def test_empty_text_is_a_no_op():
    assert humanize_references("", {"S1": "Award.pdf"}) == ""


def test_missing_filename_uses_fallback_label_supplied_by_caller():
    """The module itself just does an exact-token substitution — callers are
    responsible for mapping a token with no safe filename to
    `SAFE_FALLBACK_LABEL` before calling in.
    """
    text = "Referenced doc_x."
    result = humanize_references(text, {"doc_x": SAFE_FALLBACK_LABEL})
    assert result == f"Referenced {SAFE_FALLBACK_LABEL}."
