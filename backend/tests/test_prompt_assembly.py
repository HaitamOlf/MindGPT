from app.rag.prompt_assembly import build_system_instruction, build_system_prompt, build_user_prompt


def test_system_instruction_includes_role_and_safety_summary():
    instruction = build_system_instruction()
    assert "MindGPT" in instruction
    assert "Never diagnose mental health conditions" in instruction


def test_user_prompt_includes_user_message_last():
    prompt = build_user_prompt(user_message="I'm feeling overwhelmed today", recent_messages=[])
    assert prompt.strip().endswith("User: I'm feeling overwhelmed today")


def test_user_prompt_includes_conversation_history():
    prompt = build_user_prompt(
        user_message="And now?",
        recent_messages=[{"role": "user", "text": "I feel stuck"}, {"role": "assistant", "text": "That makes sense"}],
    )
    assert "User: I feel stuck" in prompt
    assert "Assistant: That makes sense" in prompt


def test_user_prompt_includes_retrieved_guidance_when_provided():
    prompt = build_user_prompt(
        user_message="hi",
        recent_messages=[],
        retrieved_guidance="[RETRIEVED INTERPRETIVE SCAFFOLDING]\nsome lens",
    )
    assert "[RETRIEVED INTERPRETIVE SCAFFOLDING]" in prompt


def test_system_prompt_holds_instructions_not_user_data():
    # Role separation: the system prompt carries the app's instructions; the user's message
    # and conversation turns live only in the user prompt, never the system one.
    system = build_system_prompt()
    assert "MindGPT" in system
    assert "User:" not in system


def test_system_prompt_never_contains_a_literal_crisis_placeholder():
    # Regression guard — the system prompt must never contain an unfilled placeholder
    # like "[crisis line]".
    assert "[crisis line]" not in build_system_prompt().lower()
