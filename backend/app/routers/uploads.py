"""Image upload — the one route that accepts a file. Order of checks is deliberate and
security-first (docs/ARCHITECTURE.md §7.2–7.4):

1. Auth (owner = validated JWT only).
2. Size + MIME validation — reject anything that isn't a small JPEG/PNG before doing work.
3. Content Safety image moderation — a flagged image is rejected and **never written**.
4. Store to the private `uploads` container via managed identity, under `{userId}/...`.
5. Return a short-lived, owner-scoped user-delegation SAS URL for immediate display.

The stored blob is private; it is only ever served through a freshly-minted read SAS
(here and when listing a conversation's messages), never a public URL.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field

from app.auth.dependency import get_current_user_id
from app.data.blob_store import build_blob_name, generate_read_sas_url, upload_image
from app.data.cosmos_client import get_conversation
from app.safety.content_safety import moderate_image

router = APIRouter(prefix="/uploads", tags=["uploads"])

_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
# MIME type -> canonical file extension. The allow-list is exact; nothing else is accepted.
_ALLOWED_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
}


class UploadResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    blob_name: str = Field(..., alias="blobName")
    url: str  # short-lived read SAS URL for display


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile = File(...),
    conversation_id: str | None = Form(default=None, alias="conversationId"),
    user_id: str = Depends(get_current_user_id),
) -> UploadResponse:
    content_type = (file.content_type or "").lower()
    extension = _ALLOWED_TYPES.get(content_type)
    if extension is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only JPEG and PNG images are allowed")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image exceeds the 10 MB limit")

    # If tied to a conversation, it must be one the caller owns (partition-scoped lookup).
    if conversation_id is not None and get_conversation(conversation_id, user_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if moderate_image(data).flagged:
        # Rejected before any write — the blob never touches storage.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image could not be processed")

    blob_name = build_blob_name(user_id, conversation_id or "temp", extension)
    upload_image(blob_name, data, content_type)

    url = generate_read_sas_url(blob_name, user_id)
    if url is None:  # defensive — build_blob_name always prefixes the caller's id
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not prepare the image")

    return UploadResponse(blob_name=blob_name, url=url)
