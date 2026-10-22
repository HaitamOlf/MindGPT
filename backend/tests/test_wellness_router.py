from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependency import get_current_user_id
from app.data.wellness_store import WellnessDay
from app.main import app

TEST_USER_ID = "user-abc"


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    yield TestClient(app)
    app.dependency_overrides.clear()


@patch("app.routers.wellness.list_wellness")
def test_get_returns_points_camelcase(mock_list, client):
    mock_list.return_value = [
        WellnessDay(date="2026-10-01", user_id=TEST_USER_ID, average_sentiment=0.4, sample_count=3),
        WellnessDay(date="2026-10-02", user_id=TEST_USER_ID, average_sentiment=-0.2, sample_count=1),
    ]

    response = client.get("/wellness")

    assert response.status_code == 200
    body = response.json()
    assert body == [
        {"date": "2026-10-01", "averageSentiment": 0.4},
        {"date": "2026-10-02", "averageSentiment": -0.2},
    ]
    assert mock_list.call_args[0][0] == TEST_USER_ID


@patch("app.routers.wellness.list_wellness")
def test_days_param_controls_since_date(mock_list, client):
    mock_list.return_value = []

    response = client.get("/wellness?days=7")

    assert response.status_code == 200
    since = mock_list.call_args[0][1]
    expected = (datetime.now(timezone.utc) - timedelta(days=6)).date().isoformat()
    assert since == expected


def test_days_param_is_bounded(client):
    unauth_ok = TestClient(app)
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    try:
        assert unauth_ok.get("/wellness?days=0").status_code == 422
        assert unauth_ok.get("/wellness?days=9999").status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_wellness_requires_authentication():
    unauth = TestClient(app)
    assert unauth.get("/wellness").status_code in (401, 403)
