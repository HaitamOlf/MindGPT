"""Mocked-client unit tests — see app/safety/pii.py's module docstring for the real
live-resource verification this is backed by.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.safety.pii import redact_pii


def _fake_entity(text: str, category: str, confidence: float):
    e = MagicMock()
    e.text = text
    e.category = category
    e.confidence_score = confidence
    return e


@patch("app.safety.pii._get_client")
def test_redact_pii_returns_redacted_text_and_entities(mock_get_client):
    mock_doc = MagicMock()
    mock_doc.is_error = False
    mock_doc.redacted_text = "My name is *** and I feel anxious."
    mock_doc.entities = [_fake_entity("Haitam", "Person", 0.99)]
    mock_client = MagicMock()
    mock_client.recognize_pii_entities.return_value = [mock_doc]
    mock_get_client.return_value = mock_client

    result = redact_pii("My name is Haitam and I feel anxious.")

    assert result.redacted_text == "My name is *** and I feel anxious."
    assert len(result.entities) == 1
    assert result.entities[0].category == "Person"


@patch("app.safety.pii._get_client")
def test_redact_pii_fails_closed_on_service_error(mock_get_client):
    mock_doc = MagicMock()
    mock_doc.is_error = True
    mock_doc.error = "service unavailable"
    mock_client = MagicMock()
    mock_client.recognize_pii_entities.return_value = [mock_doc]
    mock_get_client.return_value = mock_client

    with pytest.raises(RuntimeError):
        redact_pii("some text with maybe-pii")


def test_redact_pii_short_circuits_on_empty_text():
    result = redact_pii("")
    assert result.redacted_text == ""
    assert result.entities == []
