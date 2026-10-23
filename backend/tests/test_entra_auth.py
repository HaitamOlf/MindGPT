"""Exercises the real cryptographic verification path with a self-generated RSA
keypair standing in for Entra's — not a mock of validate_token itself, a mock only of
*which public key* gets fetched. Catches real bugs a pure logic-mock would hide (wrong
algorithm, wrong claim names, actual signature verification working at all).

The live tenant's endpoints (jwks_uri, issuer format) were separately verified by hand
against the real deployed tenant on 2026-10-07 — see app/auth/entra.py's docstring.
"""

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth.entra import TokenValidationError, validate_token
from app.core.config import settings

TEST_TENANT_ID = "cdae0a70-3b69-46b1-abb0-d9957189cbdd"
TEST_API_CLIENT_ID = "c1f92635-804d-4d67-9376-72b4e08080e1"
EXPECTED_ISSUER = f"https://{TEST_TENANT_ID}.ciamlogin.com/{TEST_TENANT_ID}/v2.0"


@pytest.fixture(autouse=True)
def _configure_settings():
    settings.entra_tenant_id = TEST_TENANT_ID
    settings.entra_ciam_domain = "mindgpt"
    settings.entra_api_client_id = TEST_API_CLIENT_ID
    yield


@pytest.fixture(scope="module")
def keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _make_token(keypair, **claim_overrides) -> str:
    private_key, _ = keypair
    now = int(time.time())
    claims = {
        "sub": "user-abc-123",
        "aud": TEST_API_CLIENT_ID,
        "iss": EXPECTED_ISSUER,
        "iat": now,
        "exp": now + 3600,
        **claim_overrides,
    }
    return jwt.encode(claims, private_key, algorithm="RS256")


def _mock_jwk_client(keypair):
    _, public_key = keypair
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = MagicMock(key=public_key)
    return mock_client


def test_valid_token_returns_user_id_from_sub_claim(keypair):
    token = _make_token(keypair)
    with patch("app.auth.entra._jwk_client", return_value=_mock_jwk_client(keypair)):
        result = validate_token(token)
    assert result.user_id == "user-abc-123"


def test_wrong_audience_rejected(keypair):
    token = _make_token(keypair, aud="some-other-apps-client-id")
    with patch("app.auth.entra._jwk_client", return_value=_mock_jwk_client(keypair)):
        with pytest.raises(TokenValidationError):
            validate_token(token)


def test_wrong_issuer_rejected(keypair):
    token = _make_token(keypair, iss="https://attacker-tenant.ciamlogin.com/attacker-tenant/v2.0")
    with patch("app.auth.entra._jwk_client", return_value=_mock_jwk_client(keypair)):
        with pytest.raises(TokenValidationError):
            validate_token(token)


def test_expired_token_rejected(keypair):
    now = int(time.time())
    token = _make_token(keypair, iat=now - 7200, exp=now - 3600)
    with patch("app.auth.entra._jwk_client", return_value=_mock_jwk_client(keypair)):
        with pytest.raises(TokenValidationError):
            validate_token(token)


def test_missing_sub_claim_rejected(keypair):
    private_key, _ = keypair
    now = int(time.time())
    claims = {"aud": TEST_API_CLIENT_ID, "iss": EXPECTED_ISSUER, "iat": now, "exp": now + 3600}
    token = jwt.encode(claims, private_key, algorithm="RS256")
    with patch("app.auth.entra._jwk_client", return_value=_mock_jwk_client(keypair)):
        with pytest.raises(TokenValidationError):
            validate_token(token)


def test_token_signed_by_wrong_key_rejected(keypair):
    # Simulates a forged token: signed with an attacker's key, but the real tenant's
    # (mocked) public key is what we actually check against — must fail.
    attacker_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = int(time.time())
    claims = {
        "sub": "user-abc-123",
        "aud": TEST_API_CLIENT_ID,
        "iss": EXPECTED_ISSUER,
        "iat": now,
        "exp": now + 3600,
    }
    forged_token = jwt.encode(claims, attacker_private_key, algorithm="RS256")
    with patch("app.auth.entra._jwk_client", return_value=_mock_jwk_client(keypair)):
        with pytest.raises(TokenValidationError):
            validate_token(forged_token)
