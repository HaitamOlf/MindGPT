"""Azure AI Language — PII detection/redaction before persistence or logging
(docs/ARCHITECTURE.md §7.4). Sensitive content is redacted before it is ever written to
storage or a log.

Verified against a real, live-deployed Language resource on 2026-10-06: a message
containing a name and an email came back with both correctly masked in
`redacted_text` and listed in `entities` with category + confidence.

Fails closed on a per-document service error (docs/ARCHITECTURE.md §1 "Fail closed")
rather than silently returning the original, unredacted text — a redaction failure
must block persistence/logging, not quietly skip it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from azure.ai.textanalytics import TextAnalyticsClient
from azure.identity import DefaultAzureCredential

from app.core.config import settings


@lru_cache(maxsize=1)
def _get_client() -> TextAnalyticsClient:
    credential = DefaultAzureCredential(managed_identity_client_id=settings.azure_client_id or None)
    return TextAnalyticsClient(settings.language_endpoint, credential)


@dataclass
class PiiEntity:
    text: str
    category: str
    confidence_score: float


@dataclass
class PiiResult:
    redacted_text: str
    entities: list[PiiEntity] = field(default_factory=list)


def redact_pii(text: str) -> PiiResult:
    if not text or not text.strip():
        return PiiResult(redacted_text=text)

    client = _get_client()
    results = client.recognize_pii_entities([text])
    doc = results[0]

    if doc.is_error:
        # Fail closed — the caller must not persist/log unredacted text on a service error.
        raise RuntimeError(f"PII detection failed: {doc.error}")

    entities = [
        PiiEntity(text=e.text, category=e.category, confidence_score=e.confidence_score)
        for e in doc.entities
    ]
    return PiiResult(redacted_text=doc.redacted_text, entities=entities)
