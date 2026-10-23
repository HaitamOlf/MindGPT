"""Entra External ID (CIAM) JWT validation — docs/ARCHITECTURE.md §7.2 "JWT validated
on every route (issuer, audience, signature, expiry)". The identity tenant lives under
a separate Microsoft account from everything else (§11, trust boundary ⑦ in
THREAT_MODEL.md) — that changes nothing about validation itself, since OIDC needs no
cross-tenant trust relationship, only the tenant's public OIDC metadata.

Pinned exactly, not loosely, per THREAT_MODEL.md's boundary-⑦ Spoofing entry: the
issuer check is the full tenant-ID-subdomain URL (not just "any ciamlogin.com token"),
and the audience check is this specific API's app registration ID (not just "any valid
Entra token"). Both verified against the real live tenant on 2026-10-07:
  - Discovery doc: https://mindgpt.ciamlogin.com/<tenant-id>/v2.0/.well-known/openid-configuration
  - issuer in that doc: https://<tenant-id>.ciamlogin.com/<tenant-id>/v2.0 — note this
    uses the tenant-ID subdomain, NOT the friendly "mindgpt" one, even though the
    friendly domain is what the login/jwks endpoints themselves accept. Pinning the
    friendly domain as the expected issuer would reject every real token.
  - jwks_uri: https://mindgpt.ciamlogin.com/<tenant-id>/discovery/v2.0/keys — fetched
    live and confirmed to return real RSA signing keys.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import jwt

from app.core.config import settings


class TokenValidationError(Exception):
    """Deliberately a single generic exception type — callers (the FastAPI dependency)
    must never surface the underlying reason (expired vs bad signature vs wrong
    audience) to the client. Fail closed with a generic message either way
    (docs/ARCHITECTURE.md §1 "Fail closed", §7.2 "generic error responses").
    """


@dataclass
class ValidatedToken:
    user_id: str  # the `sub` claim — pairwise, stable per user per app (tenant's
    # subject_types_supported is "pairwise", confirmed in the discovery doc)
    claims: dict


def _expected_issuer() -> str:
    return f"https://{settings.entra_tenant_id}.ciamlogin.com/{settings.entra_tenant_id}/v2.0"


def _jwks_uri() -> str:
    return f"https://{settings.entra_ciam_domain}.ciamlogin.com/{settings.entra_tenant_id}/discovery/v2.0/keys"


@lru_cache(maxsize=1)
def _jwk_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(_jwks_uri(), cache_keys=True)


def validate_token(token: str) -> ValidatedToken:
    try:
        signing_key = _jwk_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.entra_api_client_id,
            issuer=_expected_issuer(),
        )
    except jwt.PyJWTError as e:
        raise TokenValidationError(str(e)) from e

    user_id = claims.get("sub")
    if not user_id:
        raise TokenValidationError("token has no 'sub' claim")

    return ValidatedToken(user_id=user_id, claims=claims)
