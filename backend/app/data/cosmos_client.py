"""Cosmos DB conversation persistence — docs/ARCHITECTURE.md §7.3: `disableLocalAuth`,
Entra RBAC data-plane via managed identity, `userId` partition key with server-side
ownership checks (`userId` always comes from the validated JWT via the caller, never
from the request body — docs/ARCHITECTURE.md's auth non-negotiable). The partition key
field is literally named `userId` (not `user_id`) to match
infra/modules/build/cosmos-db.bicep's `partitionKey: { paths: ['/userId'] }` exactly.

Verified against the real azure-cosmos 4.17.1 SDK (CosmosClient, ContainerProxy,
CosmosResourceNotFoundError) on 2026-10-07 by installing and inspecting it directly.
Live data-plane round trip is NOT yet verified against the real deployed account — hit
the same RBAC gap Search did (Owner doesn't carry Cosmos's native data-plane roles); the
managed identity already has it correctly (cosmos-db.bicep's sqlRoleAssignments), a
human verifying locally needs their own grant, same as the Search episode.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.data._client import get_container

_CONTAINER_NAME = "conversations"

# A conversation's display title is derived from its first user message (already
# PII-redacted before it is ever persisted — see app/routers/chat.py), truncated to keep
# list payloads small. Derived text only; no separate rename endpoint exists, so no
# unused write surface is shipped.
_TITLE_MAX_LENGTH = 60
_DEFAULT_TITLE = "New conversation"


@dataclass
class Message:
    role: str  # "user" | "assistant"
    text: str
    timestamp: str
    # Blob name of an attached image (user messages only), e.g. "{userId}/{convId}/{uuid}.jpg".
    # Stored as the private blob path, never a URL — a read SAS is minted on retrieval.
    image: str | None = None

    def to_dict(self) -> dict:
        d = {"role": self.role, "text": self.text, "timestamp": self.timestamp}
        if self.image:
            d["image"] = self.image
        return d

    @staticmethod
    def from_dict(d: dict) -> "Message":
        return Message(role=d["role"], text=d["text"], timestamp=d["timestamp"], image=d.get("image"))


@dataclass
class Conversation:
    id: str
    user_id: str
    messages: list[Message] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    title: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "userId": self.user_id,  # must match the Cosmos partition key field name exactly
            "messages": [m.to_dict() for m in self.messages],
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "title": self.title,
        }

    @staticmethod
    def from_dict(d: dict) -> "Conversation":
        return Conversation(
            id=d["id"],
            user_id=d["userId"],
            messages=[Message.from_dict(m) for m in d.get("messages", [])],
            created_at=d.get("createdAt", ""),
            updated_at=d.get("updatedAt", ""),
            title=d.get("title", ""),
        )


@dataclass
class ConversationSummary:
    """A conversation without its message bodies — what the sidebar list needs. Listing
    projects only these fields server-side so one user's full transcript history is never
    pulled into memory just to render titles."""

    id: str
    title: str
    created_at: str
    updated_at: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _derive_title(messages: list[Message]) -> str:
    """First user message, trimmed to a short title. The message text is already
    PII-redacted by the time it reaches persistence, so the title inherits that."""
    for message in messages:
        if message.role == "user" and message.text.strip():
            text = " ".join(message.text.split())
            if len(text) > _TITLE_MAX_LENGTH:
                return text[: _TITLE_MAX_LENGTH - 1].rstrip() + "…"
            return text
    return _DEFAULT_TITLE


def _container():
    return get_container(_CONTAINER_NAME)


def get_conversation(conversation_id: str, user_id: str) -> Conversation | None:
    """Reads by (id, partition key) only — a conversation ID belonging to a different
    user simply doesn't exist in this user's partition, so cross-user access fails
    closed by construction, not by an application-level ownership check that could be
    forgotten (docs/ARCHITECTURE.md: "authorization enforced server-side").
    """
    try:
        doc = _container().read_item(item=conversation_id, partition_key=user_id)
    except CosmosResourceNotFoundError:
        return None
    return Conversation.from_dict(doc)


def create_conversation(user_id: str) -> Conversation:
    now = _now_iso()
    conversation = Conversation(id=str(uuid.uuid4()), user_id=user_id, created_at=now, updated_at=now)
    _container().upsert_item(conversation.to_dict())
    return conversation


def append_messages(conversation: Conversation, new_messages: list[Message]) -> Conversation:
    conversation.messages.extend(new_messages)
    conversation.updated_at = _now_iso()
    if not conversation.title:
        conversation.title = _derive_title(conversation.messages)
    _container().upsert_item(conversation.to_dict())
    return conversation


def list_conversations(user_id: str) -> list[ConversationSummary]:
    """All of one user's conversations, newest-activity first. The query is scoped to the
    user's partition (`partition_key=user_id`), so it can only ever return that user's
    own conversations — cross-user listing fails closed by construction, the same
    guarantee get_conversation relies on."""
    query = (
        "SELECT c.id, c.title, c.createdAt, c.updatedAt FROM c ORDER BY c.updatedAt DESC"
    )
    items = _container().query_items(query=query, partition_key=user_id)
    return [
        ConversationSummary(
            id=item["id"],
            title=item.get("title") or _DEFAULT_TITLE,
            created_at=item.get("createdAt", ""),
            updated_at=item.get("updatedAt", ""),
        )
        for item in items
    ]


def delete_conversation(conversation_id: str, user_id: str) -> bool:
    """Hard-delete one of the user's own conversations. Scoped to (id, partition key) so a
    conversation ID belonging to another user is simply not found here — returns False
    rather than touching anyone else's data. Returns True iff a conversation was deleted."""
    try:
        _container().delete_item(item=conversation_id, partition_key=user_id)
    except CosmosResourceNotFoundError:
        return False
    return True
