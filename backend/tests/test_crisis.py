import pytest

from app.safety.crisis import build_crisis_response, check_for_crisis, get_hotline

DETECTED_CASES = [
    "I want to kill myself",
    "I have been thinking about suicide a lot",
    "I just want to end my life",
    "I want to end it all",
    "There is no point in living anymore",
    "I feel like I would be better off dead",
    "I have been cutting myself when things get bad",
    "I cant keep going like this, so much pressure",
]

NOT_DETECTED_CASES = [
    # Close enough to trigger phrases to be a meaningful negative-case check, not detected.
    "I want to end this toxic relationship, it is ruining my life",
    "My exams are killing me this week, so much stress",
    "I am just feeling a bit anxious about work",
    "",
    "   ",
]


@pytest.mark.parametrize("message", DETECTED_CASES)
def test_detects_crisis_language(message: str):
    result = check_for_crisis(message)
    assert result.detected is True
    assert result.matched_patterns


@pytest.mark.parametrize("message", NOT_DETECTED_CASES)
def test_does_not_flag_benign_or_empty_messages(message: str):
    result = check_for_crisis(message)
    assert result.detected is False
    assert result.matched_patterns == []


def test_hotline_defaults_to_france():
    hotline = get_hotline(None)
    assert "3114" in hotline["name"]


def test_hotline_falls_back_for_unknown_region():
    hotline = get_hotline("ZZ")
    assert "International" in hotline["name"]


def test_crisis_response_never_empty_and_includes_hotline():
    response = build_crisis_response("FR")
    assert response.strip()
    assert "3114" in response
