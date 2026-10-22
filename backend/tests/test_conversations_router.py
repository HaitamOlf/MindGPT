from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependency import get_current_user_id
from app.data.cosmos_client import Conversation, ConversationSummary, Message
from app.main import app

TEST_USER_ID = "user-abc"


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    yield TestClient(app)
    app.dependency_overrides.clear()


@patch("app.routers.conversations.create_conversation")
def test_create_returns_summary_with_camelcase_fields(mock_create, client):
    mock_create.return_value = Conversation(
        id="c1", user_id=TEST_USER_ID, created_at="t0", updated_at="t0"
    )

    response = client.post("/conversations")

    assert response.status_code == 201
    body = response.json()
    assert body == {"id": "c1", "title": "New conversation", "createdAt": "t0", "updatedAt": "t0"}
    mock_create.assert_called_once_with(TEST_USER_ID)


@patch("app.routers.conversations.list_conversations")
def test_list_returns_summaries(mock_list, client):
    mock_list.return_value = [
        ConversationSummary(id="c2", title="later", created_at="t1", updated_at="t3"),
        ConversationSummary(id="c1", title="earlier", created_at="t0", updated_at="t2"),
    ]

    response = client.get("/conversations")

    assert response.status_code == 200
    body = response.json()
    assert [c["id"] for c in body] == ["c2", "c1"]
    assert body[0]["updatedAt"] == "t3"
    # listing is scoped to the authenticated user, never a body/query param
    mock_list.assert_called_once_with(TEST_USER_ID)


@patch("app.routers.conversations.get_conversation")
def test_get_messages_returns_ordered_messages(mock_get, client):
    mock_get.return_value = Conversation(
        id="c1",
        user_id=TEST_USER_ID,
        messages=[
            Message(role="user", text="hello", timestamp="t1"),
            Message(role="assistant", text="hi there", timestamp="t2"),
        ],
        created_at="t0",
        updated_at="t2",
    )

    response = client.get("/conversations/c1/messages")

    assert response.status_code == 200
    body = response.json()
    assert [m["role"] for m in body] == ["user", "assistant"]
    assert [m["id"] for m in body] == ["c1-0", "c1-1"]
    mock_get.assert_called_once_with("c1", TEST_USER_ID)


@patch("app.routers.conversations.generate_read_sas_url", return_value="https://sas-for-image")
@patch("app.routers.conversations.get_conversation")
def test_get_messages_mints_sas_for_attached_image(mock_get, mock_sas, client):
    mock_get.return_value = Conversation(
        id="c1",
        user_id=TEST_USER_ID,
        messages=[
            Message(role="user", text="look at this", timestamp="t1", image=f"{TEST_USER_ID}/c1/x.png"),
            Message(role="assistant", text="I see it", timestamp="t2"),
        ],
        created_at="t0",
        updated_at="t2",
    )

    response = client.get("/conversations/c1/messages")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["imageUrl"] == "https://sas-for-image"
    assert body[1].get("imageUrl") is None  # assistant message has no image
    mock_sas.assert_called_once_with(f"{TEST_USER_ID}/c1/x.png", TEST_USER_ID)


@patch("app.routers.conversations.get_conversation")
def test_get_messages_unknown_conversation_returns_404(mock_get, client):
    mock_get.return_value = None

    response = client.get("/conversations/missing/messages")

    assert response.status_code == 404


@patch("app.routers.conversations.delete_conversation")
def test_delete_existing_returns_204(mock_delete, client):
    mock_delete.return_value = True

    response = client.delete("/conversations/c1")

    assert response.status_code == 204
    assert response.content == b""
    mock_delete.assert_called_once_with("c1", TEST_USER_ID)


@patch("app.routers.conversations.delete_conversation")
def test_delete_missing_returns_404(mock_delete, client):
    mock_delete.return_value = False

    response = client.delete("/conversations/missing")

    assert response.status_code == 404


def test_endpoints_require_authentication():
    # No dependency override — exercises the real auth dependency on each verb.
    unauth = TestClient(app)
    assert unauth.get("/conversations").status_code in (401, 403)
    assert unauth.post("/conversations").status_code in (401, 403)
    assert unauth.get("/conversations/c1/messages").status_code in (401, 403)
    assert unauth.delete("/conversations/c1").status_code in (401, 403)
