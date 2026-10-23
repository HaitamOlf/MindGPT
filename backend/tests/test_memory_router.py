from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependency import get_current_user_id
from app.data.memory_store import MemoryItem
from app.main import app

TEST_USER_ID = "user-abc"


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    yield TestClient(app)
    app.dependency_overrides.clear()


def _item(mem_id="m1", content="remember this", source="user"):
    return MemoryItem(
        id=mem_id, user_id=TEST_USER_ID, content=content, source=source, confidence=1.0, created_at="t0"
    )


@patch("app.routers.memory.list_memories")
def test_list_returns_memories(mock_list, client):
    mock_list.return_value = [_item("m2"), _item("m1")]

    response = client.get("/memory")

    assert response.status_code == 200
    assert [m["id"] for m in response.json()] == ["m2", "m1"]
    mock_list.assert_called_once_with(TEST_USER_ID)


@patch("app.routers.memory.create_memory")
def test_create_forces_user_source(mock_create, client):
    mock_create.return_value = _item()

    response = client.post("/memory", json={"content": "remember this"})

    assert response.status_code == 201
    assert response.json()["source"] == "user"
    # a client cannot forge a "model" memory — source is always "user" here
    mock_create.assert_called_once_with(TEST_USER_ID, content="remember this", source="user")


def test_create_rejects_empty_content(client):
    response = client.post("/memory", json={"content": ""})
    assert response.status_code == 422


@patch("app.routers.memory.delete_memory")
def test_delete_existing_returns_204(mock_delete, client):
    mock_delete.return_value = True

    response = client.delete("/memory/m1")

    assert response.status_code == 204
    mock_delete.assert_called_once_with("m1", TEST_USER_ID)


@patch("app.routers.memory.delete_memory")
def test_delete_missing_returns_404(mock_delete, client):
    mock_delete.return_value = False

    response = client.delete("/memory/missing")

    assert response.status_code == 404


def test_memory_requires_authentication():
    unauth = TestClient(app)
    assert unauth.get("/memory").status_code in (401, 403)
    assert unauth.post("/memory", json={"content": "x"}).status_code in (401, 403)
    assert unauth.delete("/memory/m1").status_code in (401, 403)
