"""Retention cleanup logic, kept free of the Azure Functions runtime so it can be
unit-tested directly (function_app.py is the thin timer-trigger wrapper around it).

Why a timer trigger: a scheduled data-deletion job must have *no inbound HTTP surface* to
spoof — this runs on a timer only, so there is nothing to trigger from the internet.

Two sweeps, both runtime-free (dependencies injected) so they're unit-testable:
- `cleanup_stale_conversations` — deletes conversations in Cosmos whose last activity is
  older than the retention window.
- `cleanup_orphaned_images` — deletes uploaded image blobs no longer referenced by a live
  conversation (its conversation was deleted) or temp uploads older than the window.

Safety posture:
- DRY_RUN defaults to True — a misconfigured deploy logs what it *would* delete and
  deletes nothing.
- A non-positive retention window is refused outright, so a bad env value can never
  resolve to "delete everything".
- Each delete is isolated: one failure is logged and the run continues.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("mindgpt.cleanup")

# Matches app/data/cosmos_client.py exactly — same container, same partition-key field.
# A regression test asserts these stay in lockstep with the backend.
CONTAINER_NAME = "conversations"
PARTITION_KEY_FIELD = "userId"

# Matches app/data/blob_store.py — image blobs are `{userId}/{convId}/{uuid}.ext`, or
# `{userId}/temp/...` for an upload never attached to a conversation.
UPLOADS_CONTAINER = "uploads"
_TEMP_SEGMENT = "temp"


@dataclass
class CleanupResult:
    dry_run: bool
    retention_days: int
    cutoff: str
    scanned: int = 0
    deleted: int = 0
    deleted_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "dryRun": self.dry_run,
            "retentionDays": self.retention_days,
            "cutoff": self.cutoff,
            "scanned": self.scanned,
            "deleted": self.deleted,
            "deletedIds": self.deleted_ids,
            "errors": self.errors,
        }


def cleanup_stale_conversations(
    container,
    retention_days: int,
    *,
    dry_run: bool = True,
    now: datetime | None = None,
) -> CleanupResult:
    """Delete conversations whose `updatedAt` is older than `retention_days`.

    `container` is an azure.cosmos ContainerProxy (injected so this is testable without a
    live account). Returns a structured result for the caller to log.
    """
    if retention_days <= 0:
        # Safety lock: a non-positive window would select every conversation. Refuse
        # rather than compute a cutoff in the future and delete the whole store.
        raise ValueError(f"retention_days must be positive, got {retention_days}")

    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=retention_days)).isoformat()
    result = CleanupResult(dry_run=dry_run, retention_days=retention_days, cutoff=cutoff)

    # Cross-partition query (no partition_key): retention spans all users. Only the two
    # fields needed to delete each item are projected — never the message bodies.
    query = (
        f"SELECT c.id, c.{PARTITION_KEY_FIELD} FROM c WHERE c.updatedAt < @cutoff"
    )
    stale = container.query_items(
        query=query,
        parameters=[{"name": "@cutoff", "value": cutoff}],
    )

    for item in stale:
        result.scanned += 1
        conversation_id = item["id"]
        partition_value = item[PARTITION_KEY_FIELD]
        if dry_run:
            logger.info("[DRY RUN] would delete conversation %s", conversation_id)
            result.deleted += 1
            result.deleted_ids.append(conversation_id)
            continue
        try:
            container.delete_item(item=conversation_id, partition_key=partition_value)
            result.deleted += 1
            result.deleted_ids.append(conversation_id)
            logger.info("deleted conversation %s", conversation_id)
        except Exception as exc:  # isolate one failure from the rest of the run
            message = f"failed to delete {conversation_id}: {exc}"
            logger.error(message)
            result.errors.append(message)

    logger.info(
        "cleanup complete: scanned=%d deleted=%d errors=%d dry_run=%s",
        result.scanned,
        result.deleted,
        len(result.errors),
        dry_run,
    )
    return result


def cleanup_orphaned_images(
    blob_container,
    conversation_exists,
    retention_days: int,
    *,
    dry_run: bool = True,
    now: datetime | None = None,
) -> CleanupResult:
    """Delete uploaded image blobs no longer referenced by a live conversation.

    A blob path is `{userId}/{convId}/{uuid}.ext` (or `{userId}/temp/...` for an upload
    never attached to a conversation). A blob is orphaned when its conversation no longer
    exists (deleted by the retention sweep or the user), or when it is a temp upload older
    than the retention window.

    `blob_container` is an azure.storage.blob ContainerClient and `conversation_exists` is a
    callable `(user_id, conv_id) -> bool` — both injected so this is testable without live
    Azure. Returns a CleanupResult (deleted_ids are blob names).
    """
    if retention_days <= 0:
        raise ValueError(f"retention_days must be positive, got {retention_days}")

    now = now or datetime.now(timezone.utc)
    cutoff_dt = now - timedelta(days=retention_days)
    result = CleanupResult(dry_run=dry_run, retention_days=retention_days, cutoff=cutoff_dt.isoformat())

    for blob in blob_container.list_blobs():
        result.scanned += 1
        name = blob.name
        parts = name.split("/", 2)
        if len(parts) < 2:
            continue  # unexpected shape — leave it alone
        user_id, segment = parts[0], parts[1]

        if segment == _TEMP_SEGMENT:
            last_modified = getattr(blob, "last_modified", None)
            orphaned = last_modified is not None and last_modified < cutoff_dt
        else:
            orphaned = not conversation_exists(user_id, segment)

        if not orphaned:
            continue

        if dry_run:
            logger.info("[DRY RUN] would delete orphaned image %s", name)
            result.deleted += 1
            result.deleted_ids.append(name)
            continue
        try:
            blob_container.delete_blob(name)
            result.deleted += 1
            result.deleted_ids.append(name)
            logger.info("deleted orphaned image %s", name)
        except Exception as exc:  # isolate one failure from the rest of the run
            message = f"failed to delete image {name}: {exc}"
            logger.error(message)
            result.errors.append(message)

    logger.info(
        "orphaned-image cleanup complete: scanned=%d deleted=%d errors=%d dry_run=%s",
        result.scanned,
        result.deleted,
        len(result.errors),
        dry_run,
    )
    return result
