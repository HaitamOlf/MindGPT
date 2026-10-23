"""Azure AI Content Safety — Prompt Shields (LLM01 defense) and harm-category output
moderation (docs/ARCHITECTURE.md §7.4, §4).

Every method/field name and the api_version pin here was verified against a real,
live-deployed Content Safety resource on 2026-10-06 (not assumed from docs/memory):
- `shield_prompt` doesn't exist in the stable 1.0.0 SDK — only in the 1.1.0b1 prerelease
  (see requirements.txt comment).
- The prerelease SDK's *default* api_version (2026-09-01-preview) isn't yet supported
  on this resource's region (francecentral) and raises UnsupportedApiVersion; pinning
  api_version="2024-09-01" explicitly on client construction is what actually works for
  both shield_prompt and analyze_text — confirmed with real calls against both a benign
  and a direct-injection prompt, and benign vs. self-harm text.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.contentsafety.models import AnalyzeImageOptions, AnalyzeTextOptions, ImageData, ShieldPromptOptions
from azure.identity import DefaultAzureCredential

from app.core.config import settings

# Verified working api_version for this resource/region — see module docstring.
_API_VERSION = "2024-09-01"

# FourSeverityLevels output is 0/2/4/6. 4 ("Medium") is where content starts being
# actionable rather than borderline — tune based on real moderation review, not guessed.
_DEFAULT_SEVERITY_THRESHOLD = 4


@lru_cache(maxsize=1)
def _get_client() -> ContentSafetyClient:
    credential = DefaultAzureCredential(managed_identity_client_id=settings.azure_client_id or None)
    return ContentSafetyClient(settings.content_safety_endpoint, credential, api_version=_API_VERSION)


@dataclass
class PromptShieldResult:
    attack_detected: bool


def check_prompt_injection(user_prompt: str, documents: list[str] | None = None) -> PromptShieldResult:
    """Direct injection (user_prompt) and indirect/document injection (documents, e.g.
    ingested RAG corpus content) — docs/ARCHITECTURE.md §7.4 "Prompt Shields (direct +
    indirect/document attacks, spotlighting)".
    """
    client = _get_client()
    options = ShieldPromptOptions(user_prompt=user_prompt, documents=documents or [])
    result = client.shield_prompt(options)
    return PromptShieldResult(attack_detected=result.user_prompt_analysis.attack_detected)


@dataclass
class ModerationResult:
    flagged: bool
    category_severities: dict[str, int]


def moderate_text(text: str, severity_threshold: int = _DEFAULT_SEVERITY_THRESHOLD) -> ModerationResult:
    """Harm-category moderation — used on both user input (defense-in-depth alongside
    Prompt Shields) and model output (docs/ARCHITECTURE.md §5 sequence diagram step
    "Moderate output (harm categories)").
    """
    client = _get_client()
    result = client.analyze_text(AnalyzeTextOptions(text=text))
    severities = {cat.category: cat.severity for cat in result.categories_analysis}
    flagged = any(severity >= severity_threshold for severity in severities.values())
    return ModerationResult(flagged=flagged, category_severities=severities)


def moderate_image(image_bytes: bytes, severity_threshold: int = _DEFAULT_SEVERITY_THRESHOLD) -> ModerationResult:
    """Harm-category moderation for an uploaded image, scanned BEFORE it is ever stored
    (docs/ARCHITECTURE.md §7.4) — uploads are sensitive and may carry harmful content, so a
    flagged image is rejected and never written to Blob. Same four-severity scoring as the
    text path; verified against the live Content Safety resource's `analyze_image`.
    """
    client = _get_client()
    result = client.analyze_image(AnalyzeImageOptions(image=ImageData(content=image_bytes)))
    severities = {cat.category: cat.severity for cat in result.categories_analysis}
    flagged = any(severity >= severity_threshold for severity in severities.values())
    return ModerationResult(flagged=flagged, category_severities=severities)
