"""Retrieval + prompt formatting. An Azure AI Search query (search_client.py) returns the
most relevant corpus documents, formatted with the "[RETRIEVED INTERPRETIVE SCAFFOLDING]"
framing and an explicit "not factual claims" disclaimer — the model is grounded on them as
delimited data, never told to recite them (docs/ARCHITECTURE.md §2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.rag.search_client import query_corpus


@dataclass
class RetrievedDocument:
    title: str
    content: dict[str, Any]
    doc_type: str


@dataclass
class RetrievedGuidance:
    patterns: list[RetrievedDocument] = field(default_factory=list)
    strategies: list[RetrievedDocument] = field(default_factory=list)


def retrieve_guidance(user_message: str, top_patterns: int = 2, top_strategies: int = 1) -> RetrievedGuidance:
    raw_results = query_corpus(user_message, top=top_patterns + top_strategies + 2)

    patterns: list[RetrievedDocument] = []
    strategies: list[RetrievedDocument] = []

    for r in raw_results:
        doc = RetrievedDocument(
            title=r.get("title", "Untitled"),
            content=json.loads(r.get("content_json", "{}")),
            doc_type=r.get("type", "unknown"),
        )
        if doc.doc_type == "emotional_pattern" and len(patterns) < top_patterns:
            patterns.append(doc)
        elif doc.doc_type == "response_strategy" and len(strategies) < top_strategies:
            strategies.append(doc)

    return RetrievedGuidance(patterns=patterns, strategies=strategies)


def format_rag_context(retrieved: RetrievedGuidance) -> str:
    """Prompt-ready text. Explicitly framed as interpretive lenses, not facts to quote —
    same structural reasoning as docs/ARCHITECTURE.md §5's "corpus injected as data,
    with spotlighting", applied to retrieval output specifically.
    """
    if not retrieved.patterns and not retrieved.strategies:
        return ""

    sections = [
        "[RETRIEVED INTERPRETIVE SCAFFOLDING]",
        "",
        "The following are interpretive lenses that may help you reason about this situation.",
        "They are NOT factual claims and should NOT be quoted verbatim.",
        "Use them to guide your thinking, then respond in your own words.",
        "",
    ]

    if retrieved.patterns:
        sections.append("RELEVANT EMOTIONAL PATTERNS:")
        sections.append("")
        for i, pattern in enumerate(retrieved.patterns, 1):
            content = pattern.content
            sections.append(f"{i}. {pattern.title}")
            if "description" in content:
                sections.append(f"   Description: {content['description']}")
            if content.get("tensions"):
                sections.append(f"   Possible tensions: {', '.join(content['tensions'])}")
            if content.get("explorationAngles"):
                sections.append("   Angles to explore:")
                for angle in content["explorationAngles"][:3]:
                    sections.append(f"     - {angle}")
            if content.get("framings"):
                sections.append("   Helpful framings:")
                for framing in content["framings"][:2]:
                    sections.append(f"     - {framing}")
            sections.append("")

    if retrieved.strategies:
        sections.append("RELEVANT RESPONSE STRATEGIES:")
        sections.append("")
        for i, strategy in enumerate(retrieved.strategies, 1):
            content = strategy.content
            sections.append(f"{i}. {strategy.title}")
            if "technique" in content:
                sections.append(f"   Technique: {content['technique']}")
            if "whenToUse" in content:
                sections.append(f"   When to use: {content['whenToUse']}")
            if "howTo" in content:
                sections.append(f"   How to: {content['howTo']}")
            if content.get("examples"):
                sections.append("   Examples:")
                for example in content["examples"][:2]:
                    sections.append(f'     - "{example}"')
            sections.append("")

    sections.append("=== END RETRIEVED SCAFFOLDING ===")
    sections.append("")
    sections.append("Use these lenses to form your own response. Do not mention retrieval or documents.")
    sections.append("Choose the most relevant lens(es) or combine them as appropriate.")
    sections.append("")

    return "\n".join(sections)
