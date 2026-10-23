"""Azure AI Search client — the retrieval index backing RAG (docs/ARCHITECTURE.md §4:
"Real index; no full-collection read per message"). Uses BM25/keyword search over the
14-document corpus, which Azure AI Search's free tier serves well without an embedding
model — a genuinely working retrieval path, not a degraded fallback. An embedding
deployment (`text-embedding-3-small`) now exists, so upgrading to vector search is a
straightforward addition to `fields` + `search()`.

Index creation (management plane) was verified against the live deployed Search
resource on 2026-10-06. The upload/query (data plane) calls below are written against
the same verified SDK signatures but the live round-trip is NOT yet re-confirmed here —
see the session notes: Owner's role doesn't carry Search's data-plane RBAC the way it
does for Storage/Cosmos, and granting a data-plane role needs the user's own say.
"""

from __future__ import annotations

from functools import lru_cache

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import SearchableField, SearchFieldDataType, SearchIndex, SimpleField

from app.core.config import settings

INDEX_NAME = "mindgpt-corpus"


@lru_cache(maxsize=1)
def _credential() -> DefaultAzureCredential:
    return DefaultAzureCredential(managed_identity_client_id=settings.azure_client_id or None)


def _index_client() -> SearchIndexClient:
    return SearchIndexClient(settings.search_endpoint, _credential())


def _search_client(index_name: str = INDEX_NAME) -> SearchClient:
    return SearchClient(settings.search_endpoint, index_name, _credential())


def _corpus_index_schema(index_name: str = INDEX_NAME) -> SearchIndex:
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SimpleField(name="type", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="content_text", type=SearchFieldDataType.String),
        SimpleField(name="content_json", type=SearchFieldDataType.String),
    ]
    return SearchIndex(name=index_name, fields=fields)


def ensure_index_exists(index_name: str = INDEX_NAME) -> None:
    """Idempotent — create_or_update_index is safe to call on every deploy/startup."""
    _index_client().create_or_update_index(_corpus_index_schema(index_name))


def upload_documents(documents: list[dict], index_name: str = INDEX_NAME) -> list[tuple[str, bool]]:
    results = _search_client(index_name).upload_documents(documents)
    return [(r.key, r.succeeded) for r in results]


def query_corpus(query_text: str, top: int = 3, index_name: str = INDEX_NAME) -> list[dict]:
    """BM25 keyword search over title + content_text. Returns raw index documents
    (including `content_json`) — formatting into prompt text is retrieval.py's job,
    kept separate so this module stays a thin, testable Azure client wrapper.
    """
    client = _search_client(index_name)
    results = client.search(search_text=query_text, top=top, select=["id", "type", "title", "content_json"])
    return [dict(r) for r in results]
