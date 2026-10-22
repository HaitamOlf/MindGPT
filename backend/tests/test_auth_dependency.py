from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.auth.dependency import get_current_user_id
from app.auth.entra import TokenValidationError, ValidatedToken


def _creds(token: str) -> MagicMock:
    c = MagicMock()
    c.credentials = token
    return c


@patch("app.auth.dependency.validate_token")
def test_valid_token_returns_user_id(mock_validate):
    mock_validate.return_value = ValidatedToken(user_id="user-123", claims={})

    result = get_current_user_id(_creds("some-token"))

    assert result == "user-123"


@patch("app.auth.dependency.validate_token")
def test_invalid_token_raises_generic_401(mock_validate):
    mock_validate.side_effect = TokenValidationError("some internal reason that must not leak")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(_creds("bad-token"))

    assert exc_info.value.status_code == 401
    assert "internal reason" not in exc_info.value.detail
