"""Document-grounded RAG chatbot contracts (Phase 5).

This is document Q&A, not general immigration advice: `FeatherlessChatOutput`
may only cite `RetrievedSource` chunks that were actually retrieved for this
question, and `ChatResponse.citations` are always assembled server-side from
that retrieved set — the model selects which `source_key`s to cite, but it
never controls a citation's `filename`, `document_id`, or `excerpt` text.
Mirrors the citation-membership pattern already used by
`LLMAnalysisOutput`/`O1LLMAnalysisOutput` in `app/schemas/analysis.py`.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, model_validator

MAX_QUESTION_LENGTH = 1000
MAX_HISTORY_MESSAGES = 6
MAX_HISTORY_MESSAGE_LENGTH = 1000
MAX_HISTORY_TOTAL_CHARACTERS = 4000

DISCLAIMER_TEXT = "Proofly organizes document-derived information and is not legal advice."
INSUFFICIENT_EVIDENCE_ANSWER = "I couldn't find enough information in the uploaded documents to answer that."


class ChatHistoryMessage(BaseModel):
    """One prior turn, kept in browser state only — never persisted to
    Supermemory. Used only to interpret a follow-up question; never treated
    as documentary evidence (see `app/routers/chat.py::_build_retrieval_query`).
    """

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=MAX_HISTORY_MESSAGE_LENGTH)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_LENGTH)
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=MAX_HISTORY_MESSAGES)

    @model_validator(mode="after")
    def _history_total_length_capped(self) -> "ChatRequest":
        total = sum(len(message.content) for message in self.history)
        if total > MAX_HISTORY_TOTAL_CHARACTERS:
            raise ValueError(f"combined chat history exceeds {MAX_HISTORY_TOTAL_CHARACTERS} characters")
        return self


class RetrievedSource(BaseModel):
    """One deduplicated, normalized document chunk retrieved from the
    server-controlled Supermemory demo container. Internal only — the model
    sees this to answer/cite by `source_key`, but it is never returned to
    the frontend directly; API responses only expose the derived
    `ChatCitation`, whose fields are server-owned, not model-owned.
    """

    source_key: str
    document_id: str
    filename: str
    content: str
    page_number: int | None = None
    similarity: float | None = None


class ChatCitation(BaseModel):
    """Server-assembled citation metadata. `filename`, `document_id`, and
    `excerpt` are always looked up from the matching `RetrievedSource` by
    `source_key` — the model only ever selects which `source_key`s to cite,
    never the metadata attached to one.
    """

    source_key: str
    document_id: str
    filename: str
    page_number: int | None = None
    excerpt: str = Field(..., max_length=400)


class FeatherlessChatOutput(BaseModel):
    """Exactly the JSON shape Featherless must return for one chat answer.
    Validated with `model_validate(data, context={"valid_source_keys": {...}})`
    so an answer citing a source key that was never retrieved for this
    question fails validation the same way a malformed field would.
    """

    answer: str
    cited_source_keys: list[str] = []
    insufficient_evidence: bool = False
    needs_professional_review: bool = False

    @model_validator(mode="after")
    def _citations_reference_only_retrieved_sources(self, info: ValidationInfo) -> "FeatherlessChatOutput":
        context = info.context or {}
        valid_keys = context.get("valid_source_keys")
        if valid_keys is not None:
            unknown = set(self.cited_source_keys) - set(valid_keys)
            if unknown:
                raise ValueError(f"citations reference unknown source keys: {sorted(unknown)}")

        if self.insufficient_evidence and self.cited_source_keys:
            raise ValueError("an insufficient_evidence response must not cite any source")
        if not self.insufficient_evidence and not self.cited_source_keys:
            raise ValueError("a document_grounded answer must cite at least one source")

        return self


class ChatAnswerMode(str, Enum):
    DOCUMENT_GROUNDED = "document_grounded"
    INSUFFICIENT_DOCUMENT_EVIDENCE = "insufficient_document_evidence"


class ChatProcessingMetadata(BaseModel):
    """Safe diagnostics only — counts and flags, never a raw prompt, full
    document content, or an API key.
    """

    retrieved_source_count: int
    repair_attempted: bool = False


class ChatResponse(BaseModel):
    answer: str
    answer_mode: ChatAnswerMode
    citations: list[ChatCitation] = []
    searched_document_count: int
    disclaimer: str = DISCLAIMER_TEXT
    requires_professional_review: bool = False
    model: str | None = None
    processing: ChatProcessingMetadata
