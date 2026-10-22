from unittest.mock import MagicMock, patch

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.data.cosmos_client import (
    Conversation,
    Message,
    append_messages,
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
)


def test_conversation_roundtrip_uses_userid_key_exactly():
    # Regression guard: infra/modules/build/cosmos-db.bicep's partition key is
    # literally `/userId` — a typo here (e.g. user_id) would silently break partitioning.
    convo = Conversation(id="c1", user_id="u1", messages=[Message(role="user", text="hi", timestamp="t1")])
    d = convo.to_dict()
    assert d["userId"] == "u1"
    assert "user_id" not in d

    restored = Conversation.from_dict(d)
    assert restored.user_id == "u1"
    assert restored.messages[0].text == "hi"


@patch("app.data.cosmos_client._container")
def test_get_conversation_returns_none_when_not_found(mock_container_factory):
    mock_container = MagicMock()
    mock_container.read_item.side_effect = CosmosResourceNotFoundError()
    mock_container_factory.return_value = mock_container

    result = get_conversation("missing-id", "u1")

    assert result is None


@patch("app.data.cosmos_client._container")
def test_get_conversation_returns_parsed_conversation(mock_container_factory):
    mock_container = MagicMock()
    mock_container.read_item.return_value = {
        "id": "c1",
        "userId": "u1",
        "messages": [],
        "createdAt": "t0",
        "updatedAt": "t0",
    }
    mock_container_factory.return_value = mock_container

    result = get_conversation("c1", "u1")

    assert result.id == "c1"
    assert result.user_id == "u1"
    mock_container.read_item.assert_called_once_with(item="c1", partition_key="u1")


@patch("app.data.cosmos_client._container")
def test_create_conversation_upserts_empty_conversation(mock_container_factory):
    mock_container = MagicMock()
    mock_container_factory.return_value = mock_container

    convo = create_conversation("u1")

    assert convo.user_id == "u1"
    assert convo.messages == []
    mock_container.upsert_item.assert_called_once()
    upserted_doc = mock_container.upsert_item.call_args[0][0]
    assert upserted_doc["userId"] == "u1"


@patch("app.data.cosmos_client._container")
def test_append_messages_extends_and_upserts(mock_container_factory):
    mock_container = MagicMock()
    mock_container_factory.return_value = mock_container

    convo = Conversation(id="c1", user_id="u1", created_at="t0", updated_at="t0")
    updated = append_messages(convo, [Message(role="user", text="hello", timestamp="t1")])

    assert len(updated.messages) == 1
    assert updated.updated_at != "t0"
    mock_container.upsert_item.assert_called_once()


@patch("app.data.cosmos_client._container")
def test_append_messages_derives_title_from_first_user_message(mock_container_factory):
    mock_container_factory.return_value = MagicMock()

    convo = Conversation(id="c1", user_id="u1", created_at="t0", updated_at="t0")
    append_messages(
        convo,
        [
            Message(role="user", text="  I'm feeling  anxious about work  ", timestamp="t1"),
            Message(role="assistant", text="tell me more", timestamp="t2"),
        ],
    )

    # whitespace collapsed, taken from the user message (not the assistant reply)
    assert convo.title == "I'm feeling anxious about work"


@patch("app.data.cosmos_client._container")
def test_append_messages_truncates_long_title(mock_container_factory):
    mock_container_factory.return_value = MagicMock()

    convo = Conversation(id="c1", user_id="u1", created_at="t0", updated_at="t0")
    append_messages(convo, [Message(role="user", text="x" * 200, timestamp="t1")])

    assert len(convo.title) == 60
    assert convo.title.endswith("…")


@patch("app.data.cosmos_client._container")
def test_append_messages_preserves_existing_title(mock_container_factory):
    mock_container_factory.return_value = MagicMock()

    convo = Conversation(id="c1", user_id="u1", created_at="t0", updated_at="t0", title="My title")
    append_messages(convo, [Message(role="user", text="a new message", timestamp="t1")])

    assert convo.title == "My title"


@patch("app.data.cosmos_client._container")
def test_list_conversations_is_partition_scoped(mock_container_factory):
    mock_container = MagicMock()
    mock_container.query_items.return_value = [
        {"id": "c2", "title": "later", "createdAt": "t1", "updatedAt": "t3"},
        {"id": "c1", "title": "", "createdAt": "t0", "updatedAt": "t2"},
    ]
    mock_container_factory.return_value = mock_container

    summaries = list_conversations("u1")

    assert [s.id for s in summaries] == ["c2", "c1"]
    # a blank stored title falls back to the default rather than rendering empty
    assert summaries[1].title == "New conversation"
    # the query must target only this user's partition
    assert mock_container.query_items.call_args.kwargs["partition_key"] == "u1"


@patch("app.data.cosmos_client._container")
def test_delete_conversation_scopes_to_partition_and_returns_true(mock_container_factory):
    mock_container = MagicMock()
    mock_container_factory.return_value = mock_container

    assert delete_conversation("c1", "u1") is True
    mock_container.delete_item.assert_called_once_with(item="c1", partition_key="u1")


@patch("app.data.cosmos_client._container")
def test_delete_conversation_returns_false_when_not_found(mock_container_factory):
    mock_container = MagicMock()
    mock_container.delete_item.side_effect = CosmosResourceNotFoundError()
    mock_container_factory.return_value = mock_container

    assert delete_conversation("missing", "u1") is False
