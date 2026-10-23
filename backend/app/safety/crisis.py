"""Deterministic crisis detection. This runs in code, BEFORE the model is ever called:
a match short-circuits straight to a vetted, region-correct hotline response — crisis
handling is never left to the model's discretion, per docs/ARCHITECTURE.md §7.4 and
docs/THREAT_MODEL.md's "Deterministic crisis protocol" mitigation.

Deliberately a floor, not a ceiling: keyword matching is simple and will have false
negatives. It is intentionally tuned toward false positives over false negatives —
sb dismissed/missed crisis is categorically worse than an unnecessary hotline mention.
app/rag/guardrails.py's CRISIS_PROTOCOL text is the second line of defense for whatever
this misses, and is itself forbidden from naming a hotline (only this module may,
because only this module's hotlines are vetted and reviewed, not model-generated).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Deliberately broad and case-insensitive. Add phrases as real-world testing surfaces
# misses — never narrow this list to reduce false positives; that trades the wrong way.
_CRISIS_PATTERNS: list[re.Pattern[str]] = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bkill(ing)?\s+myself\b",
        r"\bend(ing)?\s+my\s+(own\s+)?life\b",
        r"\bend(ing)?\s+it\s+all\b",
        r"\bwant(ing)?\s+to\s+die\b",
        r"\bsuicid(e|al)\b",
        r"\bno\s+(reason|point)\s+(to|in)\s+(live|living|going on)\b",
        r"\bbetter\s+off\s+dead\b",
        r"\bhurt(ing)?\s+myself\b",
        r"\bself[\s-]?harm\b",
        r"\bcut(ting)?\s+myself\b",
        r"\bcan'?t\s+(go on|keep going|do this anymore)\b",
        r"\bdon'?t\s+want\s+to\s+(be\s+alive|live\s+anymore|exist)\b",
    ]
]

# Only hotlines that have been explicitly verified belong here — never let a model
# generate or guess one. Extend deliberately, one verified entry at a time.
_HOTLINES: dict[str, dict[str, str]] = {
    "FR": {
        "name": "3114 — Numéro national de prévention du suicide (France)",
        "contact": "Call 3114 — free, 24/7, in French",
    },
    "US": {
        "name": "988 Suicide & Crisis Lifeline (United States)",
        "contact": "Call or text 988 — free, 24/7",
    },
    "GB": {
        "name": "Samaritans (UK)",
        "contact": "Call 116 123 — free, 24/7",
    },
    "_INTERNATIONAL": {
        "name": "International Association for Suicide Prevention — crisis centre directory",
        "contact": "https://www.iasp.info/resources/Crisis_Centres/",
    },
}

_DEFAULT_REGION = "FR"  # this deployment's primary audience; never silently guess otherwise


@dataclass
class CrisisCheckResult:
    detected: bool
    matched_patterns: list[str] = field(default_factory=list)


def check_for_crisis(message: str) -> CrisisCheckResult:
    """Pure, deterministic, no external calls — must never be the slow/unreliable path
    in a safety-critical check.
    """
    if not message or not message.strip():
        return CrisisCheckResult(detected=False)

    matched = [p.pattern for p in _CRISIS_PATTERNS if p.search(message)]
    return CrisisCheckResult(detected=bool(matched), matched_patterns=matched)


def get_hotline(region: str | None = None) -> dict[str, str]:
    region_key = (region or _DEFAULT_REGION).upper()
    return _HOTLINES.get(region_key, _HOTLINES["_INTERNATIONAL"])


def build_crisis_response(region: str | None = None) -> str:
    """The exact text returned to the user in place of a model call. Calm, validating,
    unambiguous — never lecturing, never panicked (docs/THREAT_MODEL.md Crisis protocol).
    """
    hotline = get_hotline(region)
    return (
        "I'm really concerned about what you just shared, and I want to take it seriously. "
        "You deserve immediate support from someone trained to help with this.\n\n"
        f"Please reach out right now to {hotline['name']}: {hotline['contact']}\n\n"
        "If you're in immediate danger, please contact your local emergency services. "
        "Your safety matters, and reaching out for help is the right thing to do."
    )
