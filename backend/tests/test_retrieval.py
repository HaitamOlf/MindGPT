import json
from unittest.mock import patch

from app.rag.retrieval import RetrievedGuidance, format_rag_context, retrieve_guidance


def _raw_doc(doc_id: str, doc_type: str, title: str, content: dict) -> dict:
    return {"id": doc_id, "type": doc_type, "title": title, "content_json": json.dumps(content)}


@patch("app.rag.retrieval.query_corpus")
def test_retrieve_guidance_splits_patterns_and_strategies(mock_query):
    mock_query.return_value = [
        _raw_doc("pattern-0", "emotional_pattern", "Anticipatory Anxiety", {"description": "worry about the future"}),
        _raw_doc("strategy-0", "response_strategy", "Progressive Deepening", {"technique": "go deeper gradually"}),
    ]

    result = retrieve_guidance("I'm worried about tomorrow", top_patterns=2, top_strategies=1)

    assert len(result.patterns) == 1
    assert result.patterns[0].title == "Anticipatory Anxiety"
    assert len(result.strategies) == 1
    assert result.strategies[0].title == "Progressive Deepening"


@patch("app.rag.retrieval.query_corpus")
def test_retrieve_guidance_respects_top_k(mock_query):
    mock_query.return_value = [
        _raw_doc(f"pattern-{i}", "emotional_pattern", f"Pattern {i}", {}) for i in range(5)
    ]

    result = retrieve_guidance("anything", top_patterns=2, top_strategies=1)

    assert len(result.patterns) == 2


def test_format_rag_context_empty_when_no_results():
    assert format_rag_context(RetrievedGuidance()) == ""


def test_format_rag_context_includes_disclaimer_and_content():
    from app.rag.retrieval import RetrievedDocument

    guidance = RetrievedGuidance(
        patterns=[
            RetrievedDocument(
                title="Anticipatory Anxiety",
                content={"description": "worry about the future", "tensions": ["Control vs uncertainty"]},
                doc_type="emotional_pattern",
            )
        ]
    )

    text = format_rag_context(guidance)

    assert "NOT factual claims" in text
    assert "Anticipatory Anxiety" in text
    assert "worry about the future" in text
    assert "Control vs uncertainty" in text
