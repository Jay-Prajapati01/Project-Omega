"""RAG chat endpoint."""
import json
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import StreamingResponse

from app.models.schemas import ChatRequest, ChatResponse, ChatMessage, Citation, SearchHit
from app.services import compare, llm, rag, store

router = APIRouter(prefix="/chat", tags=["chat"])

EMPTY_QUESTION_ANSWER = (
    "Please enter a question so I can search your knowledge base."
)


def _charge_ai_request() -> None:
    """Apply a daily per-tenant AI request cap before calling a provider."""
    from fastapi import HTTPException
    from app.core.config import get_settings
    from app.core.ratelimit import quota_hit
    from app.core.tenant import scope

    settings = get_settings()
    if settings.mindmesh_execution_mode != "cloud":
        return
    allowed, _used = quota_hit(
        scope().tenant_id, "ai_requests", 1, settings.max_ai_requests_per_tenant_per_day
    )
    from app.core import metrics as app_metrics

    app_metrics.inc("ai_requests_total", outcome="allowed" if allowed else "rejected")
    if not allowed:
        app_metrics.inc("quota_rejected_total", kind="ai_requests")
        raise HTTPException(
            status_code=429,
            detail={"code": "AI_DAILY_QUOTA_REACHED", "message": "Daily AI request limit reached"},
            headers={"Retry-After": "3600"},
        )


class ChatActionRequest(BaseModel):
    action: Literal["explain", "notes", "flashcards", "simplify", "compare"]
    question: str = Field(..., max_length=4000)
    answer: str = Field(..., max_length=16000)
    conversation_id: str | None = Field(default=None, max_length=128)
    source_ids: list[str] = Field(default_factory=list, max_length=8)
    citations: list[Citation] = Field(default_factory=list, max_length=12)
    related_sources: list[SearchHit] = Field(default_factory=list, max_length=12)


_ACTION_PROMPTS = {
    "explain": "Explain the previous answer in more detail, using only the facts and information already present in it. Make the reasoning easier to follow; do not add outside facts.",
    "notes": "Turn the previous answer into concise, well-organized study notes. Use clear headings and bullets. Preserve the original meaning and add no facts.",
    "flashcards": "Turn the previous answer into 3 to 8 useful question-and-answer flashcards. Use the format **Q:** question followed by **A:** answer. Use only the previous answer and do not invent facts.",
    "simplify": "Rewrite the previous answer in plain, simple language. Keep all important facts and add no outside information.",
}


@router.post("/action", response_model=ChatResponse)
async def chat_action(payload: ChatActionRequest) -> ChatResponse:
    """Apply a chat action to an existing grounded answer or compare its sources."""
    from app.services.commerce import CommerceError, reserve

    action_question = payload.question.strip()
    source_ids = list(dict.fromkeys(source_id.strip() for source_id in payload.source_ids if source_id.strip()))
    if payload.action == "compare":
        if len(source_ids) < 2:
            raise HTTPException(
                status_code=422,
                detail="Compare Sources needs at least two different saved sources in this answer.",
            )
        try:
            _charge_ai_request()
            reserve("chat")
            result = await compare.compare(source_ids[0], source_ids[1])
            answer = result.get("analysis", "")
            if answer == "One or both sources have no indexed content.":
                answer = "I found two sources to compare, but one has no indexed text yet. Reprocess that source and try again."
        except CommerceError as exc:
            raise HTTPException(exc.status, {"code": exc.code, "message": str(exc)}) from None
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 — return a useful, safe action-level error
            raise HTTPException(status_code=503, detail="I couldn’t compare these sources because the AI service or indexed source content is temporarily unavailable. Try again shortly.") from exc
    else:
        if not payload.answer.strip() or payload.answer.strip() in {_NO_CONTEXT_ANSWER, _NO_MATCH_ANSWER}:
            answer = "There isn’t a relevant answer to transform yet. Ask about a topic covered by your saved content first, then try this action again."
        else:
            source_context = "\n".join(
                f"- {citation.title or citation.source_id} ({citation.source_type}): {citation.snippet[:350]}"
                for citation in payload.citations[:6]
            )
            prompt = (
                f"ORIGINAL QUESTION:\n{action_question}\n\n"
                f"GROUNDED ANSWER TO TRANSFORM:\n{payload.answer.strip()}\n\n"
                f"SOURCE NOTES (for attribution only):\n{source_context or 'No separate source notes provided.'}\n\n"
                f"TASK:\n{_ACTION_PROMPTS[payload.action]}"
            )
            try:
                _charge_ai_request()
                reserve("chat")
                answer = await llm.generate(
                    prompt,
                    system=(
                        "You are MindMesh. Transform only the supplied grounded answer. "
                        "Do not invent or add facts. Use clean Markdown, no raw numeric citation markers, "
                        "and concise, natural language. If the supplied answer says there is no matching knowledge, "
                        "do not pretend there is content to transform."
                    ),
                )
            except CommerceError as exc:
                raise HTTPException(exc.status, {"code": exc.code, "message": str(exc)}) from None
            except HTTPException:
                raise
            except Exception as exc:  # noqa: BLE001 — return a useful, safe action-level error
                raise HTTPException(status_code=503, detail=f"I couldn’t {payload.action} this answer because the AI service is temporarily unavailable. Your saved sources are unchanged; try again shortly.") from exc

    conversation_id = payload.conversation_id or str(uuid.uuid4())
    response = ChatResponse(
        question=action_question,
        conversation_id=conversation_id,
        answer=answer,
        citations=payload.citations,
        related_sources=payload.related_sources,
    )
    store.save_conversation_turn(conversation_id, response.model_dump(mode="json"))
    return response


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    import uuid
    from app.core.tenant import cloud, scope
    conversation_id = payload.conversation_id or str(
        uuid.uuid5(uuid.NAMESPACE_URL, scope().job_id) if cloud() else uuid.uuid4())
    conversation = store.get_conversation(conversation_id)
    history = payload.history
    if conversation:
        history = [message for turn in conversation["turns"][-20:] for message in (
            ChatMessage(role="user", content=turn["response"]["question"]),
            ChatMessage(role="assistant", content=turn["response"]["answer"]),
        )]
    # Blank questions get a graceful reply: no retrieval, no citations,
    # and nothing written to recent questions.
    if not payload.question:
        return ChatResponse(
            question=payload.question,
            answer=EMPTY_QUESTION_ANSWER,
            citations=[],
            related_sources=[],
            search_time_ms=0,
            chunks_searched=0,
            sources_searched=0,
        )

    from app.services.commerce import CommerceError, reserve
    try:
        _charge_ai_request()
        reserve("chat")
    except CommerceError as exc:
        raise HTTPException(exc.status, {"code": exc.code, "message": str(exc)}) from None

    store.add_question(payload.question)
    answer, citations, metrics = await rag.answer(
        payload.question,
        payload.top_k,
        source_type=payload.source_type,
        source_id=payload.source_id,
        history=history,
    )
    response = ChatResponse(
        question=payload.question,
        conversation_id=conversation_id,
        answer=answer,
        citations=citations,
        related_sources=metrics.get("related_sources", []),
        search_time_ms=metrics.get("search_time_ms"),
        chunks_searched=metrics.get("chunks_searched"),
        sources_searched=metrics.get("sources_searched"),
    )
    store.save_conversation_turn(conversation_id, response.model_dump(mode="json"))
    return response


@router.get("/conversations/{conversation_id}")
async def conversation(conversation_id: str):
    data = store.get_conversation(conversation_id)
    if data is None:
        raise HTTPException(404, "Conversation not found")
    return data


@router.post("/stream")
async def chat_stream(payload: ChatRequest):
    """Stream chat response tokens via SSE."""

    if payload.question:
        from app.services.commerce import CommerceError, reserve

        try:
            _charge_ai_request()
            reserve("chat")
        except CommerceError as exc:
            raise HTTPException(exc.status, {"code": exc.code, "message": str(exc)}) from None

    async def event_generator():
        if not payload.question:
            yield f"data: {json.dumps({'type': 'token', 'content': EMPTY_QUESTION_ANSWER})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'answer': EMPTY_QUESTION_ANSWER})}\n\n"
            return

        store.add_question(payload.question)
        full_answer = ""
        async for token in rag.answer_stream(
            payload.question,
            payload.top_k,
            source_type=payload.source_type,
            source_id=payload.source_id,
            history=payload.history,
        ):
            full_answer += token
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        # Send final metadata
        yield f"data: {json.dumps({'type': 'done', 'answer': full_answer})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
