from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependency import get_current_user_id
from app.main import app

TEST_USER_ID = "user-abc"


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user_id] = lambda: TEST_USER_ID
    yield TestClient(app)
    app.dependency_overrides.clear()


def _png(name="pic.png", content_type="image/png", data=b"\x89PNG\r\n\x1a\nfakebytes"):
    return {"file": (name, data, content_type)}


@patch("app.routers.uploads.generate_read_sas_url", return_value="https://sas-url")
@patch("app.routers.uploads.upload_image")
@patch("app.routers.uploads.moderate_image")
def test_happy_path_uploads_and_returns_sas(mock_moderate, mock_upload, mock_sas, client):
    mock_moderate.return_value = MagicMock(flagged=False)

    response = client.post("/uploads", files=_png())

    assert response.status_code == 201
    body = response.json()
    assert body["url"] == "https://sas-url"
    assert body["blobName"].startswith(f"{TEST_USER_ID}/")
    mock_upload.assert_called_once()


def test_rejects_non_image_mime(client):
    response = client.post("/uploads", files={"file": ("doc.pdf", b"%PDF", "application/pdf")})
    assert response.status_code == 400


@patch("app.routers.uploads.upload_image")
@patch("app.routers.uploads.moderate_image")
def test_oversized_image_rejected_before_storage(mock_moderate, mock_upload, client):
    big = b"x" * (10 * 1024 * 1024 + 1)
    response = client.post("/uploads", files=_png(data=big))

    assert response.status_code == 400
    mock_moderate.assert_not_called()  # size checked before any moderation/storage work
    mock_upload.assert_not_called()


@patch("app.routers.uploads.upload_image")
@patch("app.routers.uploads.moderate_image")
def test_flagged_image_is_never_stored(mock_moderate, mock_upload, client):
    mock_moderate.return_value = MagicMock(flagged=True)

    response = client.post("/uploads", files=_png())

    assert response.status_code == 400
    mock_upload.assert_not_called()  # rejected before the write


@patch("app.routers.uploads.get_conversation", return_value=None)
def test_upload_to_unknown_conversation_returns_404(mock_get, client):
    response = client.post("/uploads", files=_png(), data={"conversationId": "nope"})
    assert response.status_code == 404


def test_upload_requires_auth():
    unauth = TestClient(app)
    response = unauth.post("/uploads", files=_png())
    assert response.status_code in (401, 403)
