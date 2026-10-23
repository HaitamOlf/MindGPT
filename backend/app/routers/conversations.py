"""Conversation CRUD — the history surface the chat UX needs (create, list, read
messages, delete). Every endpoint derives the owner from the validated JWT via
`get_current_user_id` and never from the request body or path, and every Cosmos access is
scoped to that user's partition, so cross-user access fails closed by construction
(docs/ARCHITECTURE.md §7.3, the same ownership guarantee the chat router relies on).

The message-sending path lives in app/routers/chat.py; this router deliberately holds no
model, safety, or retrieval logic.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.auth.dependency import get_current_user_id
from app.data.blob_store import generate_read_sas_url
from app.data.cosmos_client import (
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationSummaryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    created_at: str = Field(..., alias="createdAt")
    updated_at: str = Field(..., alias="updatedAt")


class MessageResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # `id` is synthesized from (conversation id, position) for a stable client-side key —
    # messages are stored as an ordered array inside the conversation, not as
    # individually-identified documents, so there is no persisted message id to leak.
    id: str
    role: str
    text: str
    timestamp: str
    # Short-lived read SAS URL for an attached image, minted per request; never a stored URL.
    image_url: str | None = Field(default=None, alias="imageUrl")


@router.post("", response_model=ConversationSummaryResponse, status_code=status.HTTP_201_CREATED)
def create(user_id: str = Depends(get_current_user_id)) -> ConversationSummaryResponse:
    conversation = create_conversation(user_id)
    return ConversationSummaryResponse(
        id=conversation.id,
        title=conversation.title or "New conversation",
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.get("", response_model=list[ConversationSummaryResponse])
def list_all(user_id: str = Depends(get_current_user_id)) -> list[ConversationSummaryResponse]:
    return [
        ConversationSummaryResponse(
            id=summary.id,
            title=summary.title,
            created_at=summary.created_at,
            updated_at=summary.updated_at,
        )
        for summary in list_conversations(user_id)
    ]


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
def get_messages(conversation_id: str, user_id: str = Depends(get_current_user_id)) -> list[MessageResponse]:
    conversation = get_conversation(conversation_id, user_id)
    if conversation is None:
        # Indistinguishable from "exists but belongs to someone else" — that is the point
        # (docs/ARCHITECTURE.md: ownership enforced by the partition, not a leakable check).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return [
        MessageResponse(
            id=f"{conversation.id}-{index}",
            role=message.role,
            text=message.text,
            timestamp=message.timestamp,
            # Mint a fresh owner-scoped read SAS for any attached image (fails closed to
            # None if the blob path isn't the caller's — docs/ARCHITECTURE.md §7.3).
            image_url=generate_read_sas_url(message.image, user_id) if message.image else None,
        )
        for index, message in enumerate(conversation.messages)
    ]


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(conversation_id: str, user_id: str = Depends(get_current_user_id)) -> None:
    if not delete_conversation(conversation_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
