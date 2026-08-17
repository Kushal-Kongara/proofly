"""Deterministic replacement of known internal reference tokens (Supermemory
document IDs, chat source keys) inside model-authored narrative text.

Structured fields (`source_document_id`, `document_id`, `source_key`,
`cited_source_keys`, ...) are never touched by this module — callers apply
it only to free-text prose (summaries, limitations, gap descriptions,
answers) so a raw internal identifier can never reach the user even if the
model writes one directly into its narrative output. See Phase 6.1.
"""

from __future__ import annotations

import re

SAFE_FALLBACK_LABEL = "the cited document"


def humanize_references(text: str, label_by_token: dict[str, str]) -> str:
    """Replace every exact, whole-token occurrence of a known key in
    `label_by_token` with its mapped label.

    Whole-word matching only (`\\b...\\b`) — never a broad/partial-match
    regex — so a short key like "S1" never matches inside "S10", and a
    document ID that happens to be a substring of unrelated prose (a date,
    a receipt number) is left untouched. Unknown tokens are never replaced.
    """
    if not text or not label_by_token:
        return text

    pattern = re.compile("|".join(rf"\b{re.escape(token)}\b" for token in label_by_token))
    return pattern.sub(lambda match: label_by_token[match.group(0)], text)
