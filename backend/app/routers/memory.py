"""Memory bank — short notes the user wants MindGPT to remember, managed from the account
dashboard. `userId` comes only from the validated JWT; every read/delete is partition-
scoped, so a user only ever sees or deletes their own memories.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.auth.dependency import get_current_user_id
from app.data.memory_store import create_memory, delete_memory, list_memories

router = APIRouter(prefix="/memory", tags=["memory"])

_MAX_CONTENT = 1000


class MemoryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    content: str
    source: str
    confidence: float
    created_at: str = Field(..., alias="createdAt")


class MemoryRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=_MAX_CONTENT)


def _to_response(item) -> MemoryResponse:
    return MemoryResponse(
        id=item.id,
        content=item.content,
        source=item.source,
        confidence=item.confidence,
        created_at=item.created_at,
    )


@router.get("", response_model=list[MemoryResponse])
def list_all(user_id: str = Depends(get_current_user_id)) -> list[MemoryResponse]:
    return [_to_response(item) for item in list_memories(user_id)]


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
def create(payload: MemoryRequest, user_id: str = Depends(get_current_user_id)) -> MemoryResponse:
    # Dashboard-created memories are always "user" source — a client can't forge a
    # "model" memory, which is reserved for a future server-side extraction step.
    return _to_response(create_memory(user_id, content=payload.content, source="user"))


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(memory_id: str, user_id: str = Depends(get_current_user_id)) -> None:
    if not delete_memory(memory_id, user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
