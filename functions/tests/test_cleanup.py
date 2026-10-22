from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from cleanup import (
    CONTAINER_NAME,
    PARTITION_KEY_FIELD,
    cleanup_orphaned_images,
    cleanup_stale_conversations,
)

_NOW = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)


def test_constants_match_backend_cosmos_client():
    # Regression guard: the function and the backend must agree on container/partition
    # names, or cleanup would query the wrong place / fail to delete.
    assert CONTAINER_NAME == "conversations"
    assert PARTITION_KEY_FIELD == "userId"


def test_non_positive_retention_is_refused():
    # Safety lock: a bad window must never resolve to "delete everything".
    container = MagicMock()
    for bad in (0, -1):
        with pytest.raises(ValueError):
            cleanup_stale_conversations(container, retention_days=bad)
    container.delete_item.assert_not_called()


def test_dry_run_deletes_nothing_but_reports():
    container = MagicMock()
    container.query_items.return_value = [
        {"id": "c1", "userId": "u1"},
        {"id": "c2", "userId": "u2"},
    ]

    result = cleanup_stale_conversations(container, retention_days=90, dry_run=True, now=_NOW)

    container.delete_item.assert_not_called()
    assert result.scanned == 2
    assert result.deleted == 2  # reported as would-delete
    assert result.deleted_ids == ["c1", "c2"]


def test_wet_run_deletes_each_with_its_partition_key():
    container = MagicMock()
    container.query_items.return_value = [
        {"id": "c1", "userId": "u1"},
        {"id": "c2", "userId": "u2"},
    ]

    result = cleanup_stale_conversations(container, retention_days=30, dry_run=False, now=_NOW)

    assert result.deleted == 2
    assert container.delete_item.call_count == 2
    # each conversation deleted under its own partition key — not a single shared one
    container.delete_item.assert_any_call(item="c1", partition_key="u1")
    container.delete_item.assert_any_call(item="c2", partition_key="u2")


def test_cutoff_is_retention_days_before_now():
    container = MagicMock()
    container.query_items.return_value = []

    cleanup_stale_conversations(container, retention_days=90, dry_run=True, now=_NOW)

    params = container.query_items.call_args.kwargs["parameters"]
    cutoff = next(p["value"] for p in params if p["name"] == "@cutoff")
    assert cutoff == "2026-07-10T12:00:00+00:00"  # 90 days before _NOW


def test_one_delete_failure_does_not_abort_the_run():
    container = MagicMock()
    container.query_items.return_value = [
        {"id": "c1", "userId": "u1"},
        {"id": "c2", "userId": "u2"},
    ]
    container.delete_item.side_effect = [RuntimeError("boom"), None]

    result = cleanup_stale_conversations(container, retention_days=30, dry_run=False, now=_NOW)

    assert result.deleted == 1  # the second one still succeeded
    assert len(result.errors) == 1
    assert "c1" in result.errors[0]


# --- orphaned-image sweep ---------------------------------------------------


def _blob(name, last_modified=None):
    b = MagicMock()
    b.name = name
    b.last_modified = last_modified
    return b


def test_orphaned_image_deleted_only_when_its_conversation_is_gone():
    container = MagicMock()
    container.list_blobs.return_value = [
        _blob("u1/conv-alive/a.png"),
        _blob("u1/conv-dead/b.jpg"),
    ]
    exists = lambda uid, cid: cid == "conv-alive"  # noqa: E731

    result = cleanup_orphaned_images(container, exists, retention_days=90, dry_run=False, now=_NOW)

    assert result.deleted == 1
    container.delete_blob.assert_called_once_with("u1/conv-dead/b.jpg")


def test_temp_upload_deleted_only_when_older_than_window():
    container = MagicMock()
    container.list_blobs.return_value = [
        _blob("u1/temp/old.png", last_modified=_NOW - timedelta(days=100)),
        _blob("u1/temp/recent.png", last_modified=_NOW - timedelta(days=1)),
    ]

    result = cleanup_orphaned_images(container, lambda u, c: True, retention_days=90, dry_run=False, now=_NOW)

    assert result.deleted == 1
    container.delete_blob.assert_called_once_with("u1/temp/old.png")


def test_orphaned_image_dry_run_deletes_nothing_but_reports():
    container = MagicMock()
    container.list_blobs.return_value = [_blob("u1/conv-dead/b.jpg")]

    result = cleanup_orphaned_images(container, lambda u, c: False, retention_days=90, dry_run=True, now=_NOW)

    container.delete_blob.assert_not_called()
    assert result.deleted == 1  # reported as would-delete


def test_orphaned_image_non_positive_retention_refused():
    with pytest.raises(ValueError):
        cleanup_orphaned_images(MagicMock(), lambda u, c: True, retention_days=0)
