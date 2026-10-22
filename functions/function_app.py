"""Azure Functions app (Python v2 programming model) — timer-triggered retention cleanup.

Timer trigger only: there is no HTTP route here, which is the whole point — a scheduled
data-deletion job must have no spoofable inbound surface. Auth to Cosmos is via the
Function App's managed identity (DefaultAzureCredential), never a key — the same
identity-based posture as the backend's app/data/cosmos_client.py.

Configuration (App Settings):
- COSMOS_ENDPOINT         required — the account endpoint URI
- COSMOS_DATABASE_NAME    optional — defaults to "mindgpt"
- BLOB_ENDPOINT           optional — enables the orphaned-image sweep when set
- AZURE_CLIENT_ID         optional — user-assigned managed identity client id
- RETENTION_DAYS          optional — defaults to 90
- CLEANUP_DRY_RUN         optional — defaults to "true" (safe): logs, deletes nothing
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

import azure.functions as func
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.identity import DefaultAzureCredential

from cleanup import (
    CONTAINER_NAME,
    UPLOADS_CONTAINER,
    cleanup_orphaned_images,
    cleanup_stale_conversations,
)

logger = logging.getLogger("mindgpt.cleanup")

app = func.FunctionApp()

_DEFAULT_RETENTION_DAYS = 90
_DEFAULT_DATABASE_NAME = "mindgpt"


def _dry_run() -> bool:
    # Anything other than an explicit opt-out stays in the safe (dry-run) mode.
    return os.environ.get("CLEANUP_DRY_RUN", "true").strip().lower() not in ("false", "0", "no")


def _retention_days() -> int:
    return int(os.environ.get("RETENTION_DAYS", _DEFAULT_RETENTION_DAYS))


def _credential() -> DefaultAzureCredential:
    return DefaultAzureCredential(managed_identity_client_id=os.environ.get("AZURE_CLIENT_ID") or None)


@lru_cache(maxsize=1)
def _container():
    endpoint = os.environ["COSMOS_ENDPOINT"]
    database_name = os.environ.get("COSMOS_DATABASE_NAME", _DEFAULT_DATABASE_NAME)
    client = CosmosClient(endpoint, _credential())
    database = client.get_database_client(database_name)
    return database.get_container_client(CONTAINER_NAME)


@lru_cache(maxsize=1)
def _uploads_container():
    from azure.storage.blob import BlobServiceClient

    service = BlobServiceClient(account_url=os.environ["BLOB_ENDPOINT"], credential=_credential())
    return service.get_container_client(UPLOADS_CONTAINER)


def _conversation_exists(user_id: str, conv_id: str) -> bool:
    try:
        _container().read_item(item=conv_id, partition_key=user_id)
        return True
    except CosmosResourceNotFoundError:
        return False


# 03:00 UTC daily (NCRONTAB: second minute hour day month day-of-week).
@app.timer_trigger(arg_name="timer", schedule="0 0 3 * * *", run_on_startup=False, use_monitor=True)
def retention_cleanup(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logger.warning("retention_cleanup timer is past due; running now")

    retention_days = _retention_days()
    dry_run = _dry_run()

    conversation_result = cleanup_stale_conversations(_container(), retention_days=retention_days, dry_run=dry_run)
    logger.info("retention_cleanup (conversations) result: %s", conversation_result.as_dict())

    # Orphaned-image sweep runs only when a Blob endpoint is configured.
    if os.environ.get("BLOB_ENDPOINT"):
        image_result = cleanup_orphaned_images(
            _uploads_container(),
            _conversation_exists,
            retention_days=retention_days,
            dry_run=dry_run,
        )
        logger.info("retention_cleanup (orphaned images) result: %s", image_result.as_dict())
