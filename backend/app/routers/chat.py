"""Document-grounded RAG chatbot endpoint (Phase 5).

    User question
      -> Supermemory document-mode semantic search (SupermemoryService.search_document_chunks)
      -> validated, deduplicated document chunks (RetrievedSource)
      -> one Featherless answer call (FeatherlessService.answer_chat_question)
      -> validated citations (server-owned metadata, never model-owned)
      -> ChatResponse

This is document Q&A, not general immigration advice — see the grounding
rules baked into `_CHAT_SYSTEM_PROMPT_TEMPLATE`
(`app/services/featherless_service.py`) and `FeatherlessChatOutput`'s
citation-membership validator (`app/schemas/chat.py`). Chat turns are never
written back to Supermemory — nothing in this module calls
`upload_document`; conversation history lives only in the request body the
browser sends, never persisted server-side.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import settings
from app.schemas.chat import (
    INSUFFICIENT_EVIDENCE_ANSWER,
    ChatAnswerMode,
    ChatCitation,
    ChatHistoryMessage,
    ChatProcessingMetadata,
    ChatRequest,
    ChatResponse,
)
from app.schemas.vault_document import DocumentProcessingStatus
from app.services.featherless_service import (
    FeatherlessConfigurationError,
    FeatherlessInputTooLargeError,
    FeatherlessService,
    FeatherlessUpstreamError,
    FeatherlessValidationError,
    get_featherless_service,
)
from app.services.reference_humanizer import SAFE_FALLBACK_LABEL, humanize_references
from app.services.supermemory_service import (
    RetrievedSource,
    SupermemoryConfigurationError,
    SupermemoryService,
    SupermemoryUpstreamError,
    get_supermemory_service,
)

router = APIRouter(prefix="/api", tags=["chat"])

_EXCERPT_MAX_LENGTH = 240


def _handle_chat_error(exc: Exception) -> HTTPException:
    if isinstance(exc, (SupermemoryConfigurationError, FeatherlessConfigurationError)):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Chat is not configured")
    if isinstance(exc, FeatherlessInputTooLargeError):
        return HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Question, history, or retrieved document context is too large",
        )
    if isinstance(exc, FeatherlessValidationError):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Chat answer generation returned an invalid result")
    if isinstance(exc, (SupermemoryUpstreamError, FeatherlessUpstreamError)):
        return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Chat upstream error")
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unexpected chat error")


def _build_retrieval_query(question: str, history: list[ChatHistoryMessage]) -> str:
    """Current question plus at most the last user question — never a prior
    assistant claim, which is not documentary evidence.
    """
    last_user_message = next((turn.content for turn in reversed(history) if turn.role == "user"), None)
    if last_user_message and last_user_message.strip() != question.strip():
        return f"{last_user_message}\n{question}"
    return question


def _excerpt(content: str) -> str:
    stripped = content.strip()
    if len(stripped) <= _EXCERPT_MAX_LENGTH:
        return stripped
    truncated = stripped[:_EXCERPT_MAX_LENGTH].rsplit(" ", 1)[0]
    return f"{truncated}…"


def _insufficient_evidence_response(
    *, searched_document_count: int, retrieved_source_count: int, repair_attempted: bool = False, model: str | None = None
) -> ChatResponse:
    return ChatResponse(
        answer=INSUFFICIENT_EVIDENCE_ANSWER,
        answer_mode=ChatAnswerMode.INSUFFICIENT_DOCUMENT_EVIDENCE,
        citations=[],
        searched_document_count=searched_document_count,
        requires_professional_review=False,
        model=model,
        processing=ChatProcessingMetadata(retrieved_source_count=retrieved_source_count, repair_attempted=repair_attempted),
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    supermemory_service: SupermemoryService = Depends(get_supermemory_service),
    featherless_service: FeatherlessService = Depends(get_featherless_service),
) -> ChatResponse:
    try:
        documents = await supermemory_service.list_documents()
    except (SupermemoryConfigurationError, SupermemoryUpstreamError) as exc:
        raise _handle_chat_error(exc) from exc

    if not any(document.status == DocumentProcessingStatus.DONE for document in documents):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No processed documents are available to search.",
        )

    retrieval_query = _build_retrieval_query(request.question, request.history)

    try:
        sources: list[RetrievedSource] = await supermemory_service.search_document_chunks(
            query=retrieval_query,
            limit=settings.chat_retrieval_limit,
            threshold=settings.chat_relevance_threshold,
        )
    except (SupermemoryConfigurationError, SupermemoryUpstreamError) as exc:
        raise _handle_chat_error(exc) from exc

    searched_document_count = len({source.document_id for source in sources})

    if not sources:
        # No acceptable chunks — never call Featherless.
        return _insufficient_evidence_response(searched_document_count=0, retrieved_source_count=0)

    try:
        llm_output, repair_attempted = await featherless_service.answer_chat_question(
            question=request.question,
            history=request.history,
            sources=sources,
        )
    except (FeatherlessConfigurationError, FeatherlessInputTooLargeError, FeatherlessValidationError, FeatherlessUpstreamError) as exc:
        raise _handle_chat_error(exc) from exc

    if llm_output.insufficient_evidence or not llm_output.cited_source_keys:
        return _insufficient_evidence_response(
            searched_document_count=searched_document_count,
            retrieved_source_count=len(sources),
            repair_attempted=repair_attempted,
            model=settings.featherless_model,
        )

    source_by_key = {source.source_key: source for source in sources}
    citations = [
        ChatCitation(
            source_key=key,
            document_id=source_by_key[key].document_id,
            filename=source_by_key[key].filename,
            page_number=source_by_key[key].page_number,
            excerpt=_excerpt(source_by_key[key].content),
        )
        for key in llm_output.cited_source_keys
    ]

    # Deterministic backend-boundary enforcement: never let a raw internal
    # source key (e.g. "S1") reach the user-facing answer, even if the model
    # wrote one directly into its prose despite the prompt instruction above.
    # Labels come only from the server-controlled `sources` (never a
    # model-supplied filename), and only exact, known keys are replaced.
    label_by_source_key = {
        source.source_key: (source.filename or SAFE_FALLBACK_LABEL) for source in sources
    }
    humanized_answer = humanize_references(llm_output.answer, label_by_source_key)

    return ChatResponse(
        answer=humanized_answer,
        answer_mode=ChatAnswerMode.DOCUMENT_GROUNDED,
        citations=citations,
        searched_document_count=searched_document_count,
        requires_professional_review=llm_output.needs_professional_review,
        model=settings.featherless_model,
        processing=ChatProcessingMetadata(retrieved_source_count=len(sources), repair_attempted=repair_attempted),
    )
