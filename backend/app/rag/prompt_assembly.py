"""Structured prompt assembly (docs/ARCHITECTURE.md §2, §5). Assembles the system
instruction, grounding, retrieved corpus, and conversation context into labeled,
spotlighted sections — the "corpus as delimited data, not instructions" framing — so
untrusted content is framed as data the model reasons over, never as directives it obeys.
"""

from __future__ import annotations

from typing import Any

from app.rag.grounding import get_core_principles_summary, get_psychological_grounding
from app.rag.guardrails import get_safety_guardrails, get_safety_summary


def build_system_instruction() -> str:
    instruction = """You are MindGPT, a purpose-built emotional support assistant.

Your Role:
- Help users navigate their emotional experiences through active exploration
- Acknowledge feelings BRIEFLY, then guide toward understanding and meaning
- Form hypotheses, identify patterns, and offer new perspectives
- Take conversational initiative - don't just mirror, but guide forward
- Avoid passive validation loops and generic therapy speak

Your Approach:
- Reflect emotion in 1-2 sentences, then MOVE the conversation forward
- After validation, offer an insight, hypothesis, or new framing
- Ask targeted questions that open new directions (not "How does that feel?")
- Help users make sense of their experience, not just express it
- Be thoughtful and exploratory, not scripted or repetitive

What NOT to Do:
- Don't loop on validation without adding insight
- Don't ask obvious or generic questions
- Don't feel like a chatbot running through prompts
- Don't over-reassure or offer platitudes

{core_principles}

{safety_summary}

Remember: You are here to support and explore with the user, not to diagnose, prescribe, or replace professional care.
""".format(
        core_principles=get_core_principles_summary(),
        safety_summary=get_safety_summary(),
    )
    return instruction.strip()


def format_user_context(
    emotional_trends: str | None = None,
    recurring_themes: list[str] | None = None,
    wellness_state: dict[str, Any] | None = None,
) -> str:
    if not any([emotional_trends, recurring_themes, wellness_state]):
        return ""

    parts = ["[USER CONTEXT]"]
    if emotional_trends:
        parts.append(f"Recent Emotional Pattern: {emotional_trends}")
    if recurring_themes:
        parts.append(f"Recurring Themes: {', '.join(recurring_themes)}")
    if wellness_state:
        dominant_emotion = wellness_state.get("dominantEmotion", "")
        avg_sentiment = wellness_state.get("averageSentiment", 0)
        if dominant_emotion:
            parts.append(f"Current Wellness: {dominant_emotion} (sentiment: {avg_sentiment:.2f})")
    parts.append("")
    return "\n".join(parts)


def format_conversation_context(recent_messages: list[dict[str, str]]) -> str:
    if not recent_messages:
        return ""
    parts = []
    for msg in recent_messages:
        role = msg.get("role", "")
        text = msg.get("text", "")
        if role == "user":
            parts.append(f"User: {text}")
        elif role == "assistant":
            parts.append(f"Assistant: {text}")
    return "\n".join(parts)


def format_user_memory(selected_memories: list[str]) -> str:
    if not selected_memories:
        return ""
    parts = ["[LONG-TERM USER MEMORY]"]
    parts.extend(f"- {memory}" for memory in selected_memories)
    parts.append("")
    return "\n".join(parts)


def format_behavioral_guidelines(dataset_guidance: str) -> str:
    if not dataset_guidance or not dataset_guidance.strip():
        return ""
    return "\n".join(["[BEHAVIORAL GUIDELINES - From Knowledge Base]", dataset_guidance.strip(), ""])


def build_system_prompt() -> str:
    """The SYSTEM message — persona, behavioral principles, and safety guardrails. These are
    the application's own instructions, sent as a dedicated system role separate from (and
    higher-priority than) the user turn, so untrusted user content can't pose as a system
    directive (docs/THREAT_MODEL.md, Elevation of Privilege / LLM01)."""
    return "\n\n".join(
        [
            build_system_instruction(),
            get_psychological_grounding(),
            get_safety_guardrails(),
        ]
    ).strip()


def build_user_prompt(
    user_message: str,
    recent_messages: list[dict[str, str]],
    retrieved_guidance: str | None = None,
    has_image: bool = False,
) -> str:
    """The USER message — retrieved corpus (clearly-delimited data, already labeled by
    retrieval.py), recent conversation context, and the current message. Everything here is
    data the model reasons over, never instructions it must obey.

    Caller is responsible for crisis short-circuiting (app/safety/crisis.py) before this is
    reached, and for calling retrieve_guidance()/format_rag_context() for
    `retrieved_guidance` — this only assembles, it doesn't retrieve.
    """
    parts: list[str] = []

    if has_image:
        parts.append("[IMAGE CONTEXT] The user attached an image; consider it alongside their message.")
        parts.append("")

    if retrieved_guidance:
        parts.append(retrieved_guidance)
        parts.append("")
        parts.append(
            "(The retrieved scaffolding above is reference context — it shapes HOW you "
            "respond, not WHAT facts you assert; do not recite it as verified fact.)"
        )
        parts.append("")

    conversation_context = format_conversation_context(recent_messages)
    if conversation_context:
        parts.append(conversation_context)
        parts.append("")

    parts.append(f"User: {user_message}")

    return "\n".join(parts)
