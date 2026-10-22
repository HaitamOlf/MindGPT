"""User image uploads in Blob Storage (docs/ARCHITECTURE.md §7.3). The storage account has
`allowBlobPublicAccess:false` and `allowSharedKeyAccess:false`, so there is no public URL
and no account-key SAS possible: the API writes via its managed identity, and every read
goes through a short-lived, Entra-signed **user-delegation SAS** minted only after the
caller is confirmed to own the blob path (`{userId}/...`).

Blob names are `{userId}/{conversationId}/{uuid}.{ext}` within the private `uploads`
container — the leading `userId` segment is what makes ownership a path-prefix check.

Verified against the real azure-storage-blob 12.31.0 SDK (`get_user_delegation_key`,
`generate_blob_sas(..., user_delegation_key=...)`).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobSasPermissions, BlobServiceClient, ContentSettings, generate_blob_sas

from app.core.config import settings

_CONTAINER = "uploads"
_SAS_TTL = timedelta(hours=1)  # short-lived read link (docs: "≤1 h, user-bound")
_DELEGATION_KEY_TTL = timedelta(hours=1)


@lru_cache(maxsize=1)
def _service() -> BlobServiceClient:
    credential = DefaultAzureCredential(managed_identity_client_id=settings.azure_client_id or None)
    return BlobServiceClient(account_url=settings.blob_endpoint, credential=credential)


def build_blob_name(user_id: str, conversation_id: str, extension: str) -> str:
    """Owner-prefixed path within the uploads container; the uuid prevents collisions."""
    return f"{user_id}/{conversation_id}/{uuid.uuid4()}.{extension}"


def _owns(blob_name: str, user_id: str) -> bool:
    # A blob a user owns always begins with their id segment; anything else is not theirs.
    return blob_name.startswith(f"{user_id}/")


def download_image(blob_name: str) -> bytes:
    """Read an uploaded image's bytes back (for passing to the model's vision input). The
    caller must have already confirmed the blob belongs to the requesting user."""
    container = _service().get_container_client(_CONTAINER)
    return container.download_blob(blob_name).readall()


def upload_image(blob_name: str, data: bytes, content_type: str) -> None:
    container = _service().get_container_client(_CONTAINER)
    container.upload_blob(
        name=blob_name,
        data=data,
        overwrite=False,
        content_settings=ContentSettings(content_type=content_type),
    )


def generate_read_sas_url(blob_name: str, user_id: str) -> str | None:
    """A time-boxed read URL for one of the caller's own blobs, or None if the blob path
    isn't owned by them (fails closed — never mint a SAS for someone else's object)."""
    if not _owns(blob_name, user_id):
        return None

    service = _service()
    now = datetime.now(timezone.utc)
    delegation_key = service.get_user_delegation_key(
        key_start_time=now - timedelta(minutes=5),  # small backdate for clock skew
        key_expiry_time=now + _DELEGATION_KEY_TTL,
    )
    sas = generate_blob_sas(
        account_name=service.account_name,
        container_name=_CONTAINER,
        blob_name=blob_name,
        user_delegation_key=delegation_key,
        permission=BlobSasPermissions(read=True),
        start=now - timedelta(minutes=5),
        expiry=now + _SAS_TTL,
    )
    base = settings.blob_endpoint.rstrip("/")
    return f"{base}/{_CONTAINER}/{blob_name}?{sas}"
