"""Message sentiment scoring via Azure AI Language (the same resource app/safety/pii.py
uses). Produces the signal the wellness trend is built from.

**Fails open, deliberately** — this is the opposite of pii.py. PII redaction fails *closed*
because leaking unredacted text is a security harm; wellness is an ancillary analytics
feature, so a Language-service hiccup must never break the chat request it piggybacks on.
On any error this returns None and the caller simply records no sample for that message.

Verified method/shape against the real azure-ai-textanalytics 5.4.0 SDK (`analyze_sentiment`
→ per-doc `.is_error` / `.confidence_scores.{positive,neutral,negative}`), matching the
same DictMixin result pattern pii.py relies on.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from azure.ai.textanalytics import TextAnalyticsClient
from azure.identity import DefaultAzureCredential

from app.core.config import settings

logger = logging.getLogger("mindgpt.sentiment")


@lru_cache(maxsize=1)
def _get_client() -> TextAnalyticsClient:
    credential = DefaultAzureCredential(managed_identity_client_id=settings.azure_client_id or None)
    return TextAnalyticsClient(settings.language_endpoint, credential)


def analyze_sentiment_score(text: str) -> float | None:
    """A sentiment score in [-1.0, 1.0] (positive confidence minus negative confidence),
    or None if the text is empty or the service is unavailable. Never raises."""
    if not text or not text.strip():
        return None
    try:
        results = _get_client().analyze_sentiment([text])
        doc = results[0]
        if doc.is_error:
            logger.warning("sentiment analysis returned an error document: %s", doc.error)
            return None
        scores = doc.confidence_scores
        return round(scores.positive - scores.negative, 4)
    except Exception as exc:  # fail open — wellness must never break the chat flow
        logger.warning("sentiment analysis unavailable, skipping sample: %s", exc)
        return None
