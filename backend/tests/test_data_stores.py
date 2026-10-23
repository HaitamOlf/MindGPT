"""Store-level tests for the profile / memory / wellness Cosmos stores — partition
scoping, document shape (camelCase + `userId` partition field), and the wellness running
average. External Cosmos access is mocked via each store's `_container`."""

from unittest.mock import MagicMock, patch

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.data import memory_store, profile_store, wellness_store


# --- profile ---------------------------------------------------------------

@patch("app.data.profile_store._container")
def test_profile_doc_id_equals_userid(mock_container_factory):
    mock_container = MagicMock()
    mock_container_factory.return_value = mock_container

    profile_store.upsert_profile("u1", full_name="A", date_of_birth="01/02/2000", country="France")

    doc = mock_container.upsert_item.call_args[0][0]
    assert doc["id"] == "u1"  # one profile per user: id == partition key
    assert doc["userId"] == "u1"
    assert doc["fullName"] == "A"
    assert doc["completedAt"]  # stamped


@patch("app.data.profile_store._container")
def test_get_profile_returns_none_when_missing(mock_container_factory):
    mock_container = MagicMock()
    mock_container.read_item.side_effect = CosmosResourceNotFoundError()
    mock_container_factory.return_value = mock_container

    assert profile_store.get_profile("u1") is None
    mock_container.read_item.assert_called_once_with(item="u1", partition_key="u1")


# --- memory ----------------------------------------------------------------

@patch("app.data.memory_store._container")
def test_list_memories_is_partition_scoped(mock_container_factory):
    mock_container = MagicMock()
    mock_container.query_items.return_value = [
        {"id": "m1", "userId": "u1", "content": "hi", "source": "user", "confidence": 1.0, "createdAt": "t1"},
    ]
    mock_container_factory.return_value = mock_container

    items = memory_store.list_memories("u1")

    assert items[0].id == "m1"
    assert mock_container.query_items.call_args.kwargs["partition_key"] == "u1"


@patch("app.data.memory_store._container")
def test_create_memory_defaults_to_user_source(mock_container_factory):
    mock_container = MagicMock()
    mock_container_factory.return_value = mock_container

    item = memory_store.create_memory("u1", content="remember")

    assert item.source == "user"
    assert item.confidence == 1.0
    doc = mock_container.upsert_item.call_args[0][0]
    assert doc["userId"] == "u1"


@patch("app.data.memory_store._container")
def test_delete_memory_scopes_to_partition(mock_container_factory):
    mock_container = MagicMock()
    mock_container_factory.return_value = mock_container

    assert memory_store.delete_memory("m1", "u1") is True
    mock_container.delete_item.assert_called_once_with(item="m1", partition_key="u1")


@patch("app.data.memory_store._container")
def test_delete_memory_returns_false_when_missing(mock_container_factory):
    mock_container = MagicMock()
    mock_container.delete_item.side_effect = CosmosResourceNotFoundError()
    mock_container_factory.return_value = mock_container

    assert memory_store.delete_memory("missing", "u1") is False


# --- wellness --------------------------------------------------------------

@patch("app.data.wellness_store._container")
def test_record_sentiment_creates_day_when_absent(mock_container_factory):
    mock_container = MagicMock()
    mock_container.read_item.side_effect = CosmosResourceNotFoundError()
    mock_container_factory.return_value = mock_container

    day = wellness_store.record_sentiment("u1", 0.6, "2026-10-08")

    assert day.average_sentiment == 0.6
    assert day.sample_count == 1
    doc = mock_container.upsert_item.call_args[0][0]
    assert doc["id"] == "2026-10-08"  # id == date
    assert doc["userId"] == "u1"


@patch("app.data.wellness_store._container")
def test_record_sentiment_updates_running_average(mock_container_factory):
    mock_container = MagicMock()
    mock_container.read_item.return_value = {
        "id": "2026-10-08",
        "userId": "u1",
        "date": "2026-10-08",
        "averageSentiment": 0.6,
        "sampleCount": 1,
    }
    mock_container_factory.return_value = mock_container

    day = wellness_store.record_sentiment("u1", 0.0, "2026-10-08")

    # running mean of 0.6 (n=1) and 0.0 => 0.3 over n=2
    assert day.sample_count == 2
    assert day.average_sentiment == 0.3


@patch("app.data.wellness_store._container")
def test_list_wellness_is_partition_scoped_with_since(mock_container_factory):
    mock_container = MagicMock()
    mock_container.query_items.return_value = []
    mock_container_factory.return_value = mock_container

    wellness_store.list_wellness("u1", "2026-01-01")

    kwargs = mock_container.query_items.call_args.kwargs
    assert kwargs["partition_key"] == "u1"
    assert kwargs["parameters"] == [{"name": "@since", "value": "2026-01-01"}]
