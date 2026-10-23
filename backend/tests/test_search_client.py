"""Mocked-client unit tests. Index-creation (management plane) was verified live
against the deployed Search resource — see app/rag/search_client.py's module
docstring; the data-plane round-trip (upload/query) is pending a role grant decision
and is not yet live-verified, so these tests lock in the wrapper logic only.
"""

from unittest.mock import MagicMock, patch

from app.rag.search_client import ensure_index_exists, query_corpus, upload_documents


@patch("app.rag.search_client._index_client")
def test_ensure_index_exists_calls_create_or_update(mock_index_client_factory):
    mock_client = MagicMock()
    mock_index_client_factory.return_value = mock_client

    ensure_index_exists("test-index")

    mock_client.create_or_update_index.assert_called_once()
    created_index = mock_client.create_or_update_index.call_args[0][0]
    assert created_index.name == "test-index"


@patch("app.rag.search_client._search_client")
def test_upload_documents_returns_key_success_pairs(mock_search_client_factory):
    mock_result_ok = MagicMock(key="1", succeeded=True)
    mock_result_fail = MagicMock(key="2", succeeded=False)
    mock_client = MagicMock()
    mock_client.upload_documents.return_value = [mock_result_ok, mock_result_fail]
    mock_search_client_factory.return_value = mock_client

    results = upload_documents([{"id": "1"}, {"id": "2"}])

    assert results == [("1", True), ("2", False)]


@patch("app.rag.search_client._search_client")
def test_query_corpus_returns_list_of_dicts(mock_search_client_factory):
    mock_client = MagicMock()
    mock_client.search.return_value = [
        {"id": "pattern-0", "type": "emotional_pattern", "title": "Anticipatory Anxiety", "content_json": "{}"}
    ]
    mock_search_client_factory.return_value = mock_client

    results = query_corpus("worried about the future")

    assert len(results) == 1
    assert results[0]["title"] == "Anticipatory Anxiety"
