from unittest.mock import patch

from app.core.config import settings
from app.llm.provider import AzureOpenAIProvider, LocalStubProvider, get_llm_provider


def test_local_stub_generate_is_clearly_labeled_as_a_stub():
    reply = LocalStubProvider().generate("system instructions", "hello")
    assert "stub" in reply.lower()


def test_local_stub_embed_is_deterministic():
    provider = LocalStubProvider()
    assert provider.embed("same text") == provider.embed("same text")
    assert provider.embed("text a") != provider.embed("text b")


def test_factory_returns_local_stub_when_no_openai_endpoint_configured():
    get_llm_provider.cache_clear()
    settings.azure_openai_endpoint = ""
    try:
        assert isinstance(get_llm_provider(), LocalStubProvider)
    finally:
        get_llm_provider.cache_clear()


def test_factory_returns_azure_provider_when_endpoint_configured():
    get_llm_provider.cache_clear()
    settings.azure_openai_endpoint = "https://example.openai.azure.com/"
    try:
        # Don't build a real client (no creds/SDK call in a unit test).
        with patch.object(AzureOpenAIProvider, "__init__", return_value=None):
            assert isinstance(get_llm_provider(), AzureOpenAIProvider)
    finally:
        settings.azure_openai_endpoint = ""
        get_llm_provider.cache_clear()
