from unittest.mock import MagicMock, patch

from app.analysis.sentiment import analyze_sentiment_score


def _doc(positive, negative, is_error=False):
    doc = MagicMock()
    doc.is_error = is_error
    doc.confidence_scores = MagicMock(positive=positive, negative=negative)
    return doc


def test_empty_text_returns_none_without_calling_service():
    with patch("app.analysis.sentiment._get_client") as mock_client:
        assert analyze_sentiment_score("   ") is None
        mock_client.assert_not_called()


@patch("app.analysis.sentiment._get_client")
def test_score_is_positive_minus_negative(mock_client):
    mock_client.return_value.analyze_sentiment.return_value = [_doc(0.9, 0.05)]

    assert analyze_sentiment_score("I feel great") == 0.85


@patch("app.analysis.sentiment._get_client")
def test_error_document_fails_open_to_none(mock_client):
    mock_client.return_value.analyze_sentiment.return_value = [_doc(0, 0, is_error=True)]

    assert analyze_sentiment_score("whatever") is None


@patch("app.analysis.sentiment._get_client")
def test_service_exception_fails_open_to_none(mock_client):
    # The opposite of PII (which fails closed): a Language outage must never raise into the
    # chat flow — wellness is ancillary.
    mock_client.return_value.analyze_sentiment.side_effect = RuntimeError("service down")

    assert analyze_sentiment_score("hello") is None
