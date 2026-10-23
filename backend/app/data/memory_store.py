"""User "memory bank" persistence (Cosmos `memory` container). Each item is a short note
the user (or, in a future pipeline hook, the model) wants remembered across conversations.
Partitioned by `/userId`; every read/delete is partition-scoped, so items are only ever
visible to their owner.

`source` is "user" for notes the person adds in the dashboard and "model" reserved for
model-extracted memories — the store supports both, but the chat pipeline writing "model"
memories is a deliberately deferred follow-up, not built here (nothing fabricates them).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.data._client import get_container

_CONTAINER_NAME = "memory"


def _container():
    return get_container(_CONTAINER_NAME)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class MemoryItem:
    id: str
    user_id: str
    content: str
    source: str  # "user" | "model"
    confidence: float
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "userId": self.user_id,
            "content": self.content,
            "source": self.source,
            "confidence": self.confidence,
            "createdAt": self.created_at,
        }

    @staticmethod
    def from_dict(d: dict) -> "MemoryItem":
        return MemoryItem(
            id=d["id"],
            user_id=d["userId"],
            content=d.get("content", ""),
            source=d.get("source", "user"),
            confidence=d.get("confidence", 1.0),
            created_at=d.get("createdAt", ""),
        )


def list_memories(user_id: str) -> list[MemoryItem]:
    query = "SELECT * FROM c ORDER BY c.createdAt DESC"
    items = _container().query_items(query=query, partition_key=user_id)
    return [MemoryItem.from_dict(item) for item in items]


def create_memory(user_id: str, content: str, source: str = "user", confidence: float = 1.0) -> MemoryItem:
    item = MemoryItem(
        id=str(uuid.uuid4()),
        user_id=user_id,
        content=content,
        source=source,
        confidence=confidence,
        created_at=_now_iso(),
    )
    _container().upsert_item(item.to_dict())
    return item


def delete_memory(memory_id: str, user_id: str) -> bool:
    """Delete one of the user's own memories. Scoped to (id, partition key), so an id from
    another user's partition is simply not found. Returns True iff something was deleted."""
    try:
        _container().delete_item(item=memory_id, partition_key=user_id)
    except CosmosResourceNotFoundError:
        return False
    return True
