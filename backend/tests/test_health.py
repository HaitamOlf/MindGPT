from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_requires_no_auth():
    response = client.get("/health", headers={})
    assert response.status_code == 200


def test_security_headers_present_on_every_response():
    # Transport hardening added after the DAST pass flagged them missing
    # (security/dast_probe.py, docs/SECURITY_VALIDATION.md).
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "max-age=" in response.headers["strict-transport-security"]
    assert response.headers["referrer-policy"] == "no-referrer"


def test_interactive_docs_disabled_by_default():
    # Recon-surface reduction (security/dast_probe.py): docs/schema are off unless
    # ENABLE_API_DOCS=true. The test env sets no override, so they must be 404.
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
