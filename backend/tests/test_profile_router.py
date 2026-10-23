from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependency import get_current_user_id
from app.data.profile_store import Profile
from app.main import app

TEST_USER_ID = "user-abc"


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    yield TestClient(app)
    app.dependency_overrides.clear()


@patch("app.routers.profile.get_profile")
def test_get_returns_profile_camelcase(mock_get, client):
    mock_get.return_value = Profile(
        user_id=TEST_USER_ID,
        full_name="Alex Chen",
        date_of_birth="01/02/2000",
        country="France",
        completed_at="t0",
    )

    response = client.get("/profile")

    assert response.status_code == 200
    assert response.json() == {
        "fullName": "Alex Chen",
        "dateOfBirth": "01/02/2000",
        "country": "France",
        "completedAt": "t0",
    }
    mock_get.assert_called_once_with(TEST_USER_ID)


@patch("app.routers.profile.get_profile")
def test_get_unset_profile_returns_404(mock_get, client):
    mock_get.return_value = None

    response = client.get("/profile")

    assert response.status_code == 404


@patch("app.routers.profile.upsert_profile")
def test_put_upserts_and_returns_profile(mock_upsert, client):
    mock_upsert.return_value = Profile(
        user_id=TEST_USER_ID,
        full_name="Alex Chen",
        date_of_birth="01/02/2000",
        country="France",
        completed_at="t1",
    )

    response = client.put(
        "/profile",
        json={"fullName": "Alex Chen", "dateOfBirth": "01/02/2000", "country": "France"},
    )

    assert response.status_code == 200
    assert response.json()["completedAt"] == "t1"
    # userId is taken from the token, never the body
    mock_upsert.assert_called_once_with(
        TEST_USER_ID, full_name="Alex Chen", date_of_birth="01/02/2000", country="France"
    )


def test_put_rejects_empty_name(client):
    response = client.put(
        "/profile", json={"fullName": "", "dateOfBirth": "01/02/2000", "country": "France"}
    )
    assert response.status_code == 422


def test_profile_requires_authentication():
    unauth = TestClient(app)
    assert unauth.get("/profile").status_code in (401, 403)
    assert unauth.put(
        "/profile", json={"fullName": "x", "dateOfBirth": "01/02/2000", "country": "France"}
    ).status_code in (401, 403)
