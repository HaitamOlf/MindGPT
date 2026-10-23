"""The request pipeline — docs/ARCHITECTURE.md §5's sequence diagram, plus the
deterministic crisis short-circuit added in Phase 3 (not in the original diagram, which
predates app/safety/crisis.py). Order matters and is deliberate:

1. Auth (user_id from the validated JWT only — never the request body)
2. Crisis check — cheapest, most safety-critical; short-circuits before anything else
   touches Content Safety, retrieval, or the model
3. Prompt Shields — refuse with no model call on a detected injection
4. PII redaction — computed for storage/logs; retrieval and prompt assembly still use
   the original message text (docs/ARCHITECTURE.md §7.4: redacted "before persistence
   or logging", not before processing)
5. Retrieval + prompt assembly
6. LLMProvider.generate — the local stub today; see app/llm/provider.py
7. Output moderation — fails closed: a flagged reply is never shown to the user
8. Persist (partition = userId) and respond
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.analysis.sentiment import analyze_sentiment_score
from app.auth.dependency import get_current_user_id
from app.data.blob_store import download_image
from app.data.cosmos_client import Conversation, Message, append_messages, create_conversation, get_conversation
from app.data.wellness_store import record_sentiment
from app.llm.provider import get_llm_provider
from app.rag.prompt_assembly import build_system_prompt, build_user_prompt
from app.rag.retrieval import format_rag_context, retrieve_guidance
from app.safety.content_safety import check_prompt_injection, moderate_text
from app.safety.crisis import build_crisis_response, check_for_crisis
from app.safety.pii import redact_pii

logger = logging.getLogger("mindgpt.chat")

router = APIRouter(prefix="/chat", tags=["chat"])

_RECENT_MESSAGE_COUNT = 6
# Generous enough for real use, bounded so one request can't blow up embedding/model
# cost or storage — docs/ARCHITECTURE.md §7.2 "length/size/MIME validation".
_MAX_MESSAGE_LENGTH = 4000

_MODERATION_FALLBACK_REPLY = (
    "I'm not able to share that response as written. Could we come at this from a "
    "different angle?"
)


class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str = Field(..., min_length=1, max_length=_MAX_MESSAGE_LENGTH)
    conversation_id: str | None = Field(default=None, alias="conversationId")
    # Blob name of an image previously uploaded via POST /uploads (already moderated there).
    image_blob_name: str | None = Field(default=None, alias="imageBlobName")


class ChatResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    reply: str
    conversation_id: str = Field(..., alias="conversationId")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_image_data_url(image_ref: str | None) -> str | None:
    """Download an attached image and inline it as a base64 data URL for the model's vision
    input (gpt-5-mini is multimodal). Best-effort: on any error the chat proceeds text-only
    rather than failing — the reply just won't reference the image."""
    if not image_ref:
        return None
    try:
        data = download_image(image_ref)
        ext = image_ref.rsplit(".", 1)[-1].lower()
        mime = "image/png" if ext == "png" else "image/jpeg"
        return f"data:{mime};base64,{base64.b64encode(data).decode()}"
    except Exception as exc:  # fail open — an image-load failure must not break the chat
        logger.warning("could not load attached image %s for the model: %s", image_ref, exc)
        return None


def _record_wellness_sample(user_id: str, message: str) -> None:
    """Best-effort: fold this message's sentiment into today's wellness aggregate. Never
    raises — wellness is an ancillary analytics feature and must not affect the chat
    response (app/analysis/sentiment.py fails open). Only the derived score is persisted,
    never the message text (data minimization). Runs only on the normal path, so crisis
    and injection messages are deliberately not scored."""
    score = analyze_sentiment_score(message)
    if score is None:
        return
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        record_sentiment(user_id, score, today)
    except Exception as exc:
        logger.warning("could not record wellness sample: %s", exc)


def _resolve_conversation(conversation_id: str | None, user_id: str) -> Conversation:
    if conversation_id is None:
        return create_conversation(user_id)
    conversation = get_conversation(conversation_id, user_id)
    if conversation is None:
        # Partition-scoped lookup (docs/ARCHITECTURE.md: fails closed by construction) —
        # this is "no such conversation for this user," not distinguishable from "exists
        # but belongs to someone else," which is exactly the point.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.post("", response_model=ChatResponse)
def send_message(payload: ChatRequest, user_id: str = Depends(get_current_user_id)) -> ChatResponse:
    conversation = _resolve_conversation(payload.conversation_id, user_id)

    # An attached image must live under the caller's own blob prefix — reject a reference to
    # anyone else's object before it's ever persisted (the read-side SAS also fails closed).
    image_ref = payload.image_blob_name
    if image_ref is not None and not image_ref.startswith(f"{user_id}/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image reference")

    crisis_result = check_for_crisis(payload.message)
    if crisis_result.detected:
        reply_text = build_crisis_response()
        append_messages(
            conversation,
            [
                Message(
                    role="user",
                    text=redact_pii(payload.message).redacted_text,
                    timestamp=_now_iso(),
                    image=image_ref,
                ),
                Message(role="assistant", text=reply_text, timestamp=_now_iso()),
            ],
        )
        return ChatResponse(reply=reply_text, conversation_id=conversation.id)

    injection_result = check_prompt_injection(payload.message)
    if injection_result.attack_detected:
        # No persistence, no model call — matches docs/ARCHITECTURE.md §5's "attack
        # detected" branch exactly. Structured safety-event logging (App Insights) is a
        # later item; deliberately not faked here with print().
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message could not be processed")

    redacted_user_text = redact_pii(payload.message).redacted_text

    recent_messages = [
        {"role": m.role, "text": m.text} for m in conversation.messages[-_RECENT_MESSAGE_COUNT:]
    ]
    image_data_url = _load_image_data_url(image_ref)

    guidance = retrieve_guidance(payload.message)
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(
        user_message=payload.message,
        recent_messages=recent_messages,
        retrieved_guidance=format_rag_context(guidance),
        has_image=image_data_url is not None,
    )

    raw_reply = get_llm_provider().generate(system_prompt, user_prompt, image_data_url=image_data_url)

    moderation_result = moderate_text(raw_reply)
    final_reply = _MODERATION_FALLBACK_REPLY if moderation_result.flagged else raw_reply

    append_messages(
        conversation,
        [
            Message(role="user", text=redacted_user_text, timestamp=_now_iso(), image=image_ref),
            Message(role="assistant", text=final_reply, timestamp=_now_iso()),
        ],
    )

    _record_wellness_sample(user_id, payload.message)

    return ChatResponse(reply=final_reply, conversation_id=conversation.id)
