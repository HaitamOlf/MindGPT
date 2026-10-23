"""LLMProvider interface — docs/ARCHITECTURE.md §8 "LLM access contingency". The chat
router is built against this interface, not a concrete provider, so it works whether or
not a real model is deployed: when `AZURE_OPENAI_ENDPOINT` is configured the factory
returns `AzureOpenAIProvider`, otherwise `LocalStubProvider` (dev/CI; tests never need a
live model).

Auth is Entra-only — the OpenAI resource has `disableLocalAuth:true` (no API keys), so the
client uses a `DefaultAzureCredential` bearer-token provider (managed identity in Azure,
az-CLI login locally), scoped to the Cognitive Services audience.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from functools import lru_cache

from app.core.config import settings


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, image_data_url: str | None = None) -> str: ...

    @abstractmethod
    def embed(self, text: str) -> list[float]: ...


class LocalStubProvider(LLMProvider):
    """Dev/CI stub — docs/ARCHITECTURE.md §8: "a local stub for dev/CI so tests never
    require a live model." Deliberately and visibly NOT a real response, so it's never
    mistaken for one in logs or during manual testing.
    """

    def generate(self, system_prompt: str, user_prompt: str, image_data_url: str | None = None) -> str:
        return (
            "[local stub LLM — no real model connected; Azure OpenAI isn't deployed on "
            "this subscription] I hear you, and I want to respond thoughtfully to that."
        )

    def embed(self, text: str) -> list[float]:
        # Deterministic, not random — reproducible in tests. Not semantically meaningful;
        # only exists so code depending on the interface has something real to call.
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [b / 255.0 for b in digest[:16]]


class AzureOpenAIProvider(LLMProvider):
    """Real inference against the Azure OpenAI deployment (gpt-5-mini chat +
    text-embedding-3-small). Entra-authenticated, no keys. The persona/safety instructions
    go in a dedicated `system` message and the user's content (corpus-as-data + history +
    message) in the `user` message — so untrusted input can't impersonate a system
    directive. Prompt-injection defense is also handled upstream by Content Safety Prompt
    Shields before this is ever called.
    """

    # gpt-5 is a reasoning model: it rejects a custom `temperature` (only the default is
    # allowed) and uses `max_completion_tokens`, which also covers reasoning tokens — hence
    # a generous bound rather than a tight one.
    _MAX_COMPLETION_TOKENS = 2000

    def __init__(self) -> None:
        # Imported lazily so the module (and LocalStubProvider / CI) never needs the SDK or
        # Azure creds just to import this file.
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        from openai import AzureOpenAI

        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(managed_identity_client_id=settings.azure_client_id or None),
            "https://cognitiveservices.azure.com/.default",
        )
        self._client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            azure_ad_token_provider=token_provider,
            api_version=settings.azure_openai_api_version,
        )

    def generate(self, system_prompt: str, user_prompt: str, image_data_url: str | None = None) -> str:
        # When an image is attached, the user turn becomes multimodal content (gpt-5-mini is
        # vision-capable); the image is inlined as a base64 data URL by the caller so the
        # model never has to reach the private blob. It was content-safety-scanned at upload.
        if image_data_url:
            user_content: object = [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ]
        else:
            user_content = user_prompt

        response = self._client.chat.completions.create(
            model=settings.azure_openai_chat_deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            max_completion_tokens=self._MAX_COMPLETION_TOKENS,
        )
        return response.choices[0].message.content or ""

    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(
            model=settings.azure_openai_embedding_deployment,
            input=text,
        )
        return response.data[0].embedding


@lru_cache(maxsize=1)
def get_llm_provider() -> LLMProvider:
    if settings.azure_openai_endpoint:
        return AzureOpenAIProvider()
    return LocalStubProvider()
