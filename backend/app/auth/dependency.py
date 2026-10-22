"""FastAPI wiring for app/auth/entra.py — the only place a route handler should ever
touch auth. docs/ARCHITECTURE.md non-negotiable: `userId` is derived only from the
validated token, never from the request body — routers get a `user_id` string from
this dependency and nothing else.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.entra import TokenValidationError, validate_token

_bearer_scheme = HTTPBearer()


def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme)) -> str:
    try:
        validated = validate_token(credentials.credentials)
    except TokenValidationError:
        # Generic message only — never the underlying reason (docs/ARCHITECTURE.md §7.2).
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return validated.user_id
