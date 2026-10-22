from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Mirrors exactly the env vars infra/modules/build/container-apps.bicep injects into
    the Container App. Field names are case-insensitive matches of the bicep env var
    names — see that file before changing either side.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    azure_client_id: str = ""
    applicationinsights_connection_string: str = ""

    # Entra External ID (CIAM) — lives in a separate tenant/account from everything
    # else here; see docs/ARCHITECTURE.md §11 for why. Real tenant, verified live
    # against its OIDC discovery doc on 2026-10-07.
    entra_tenant_id: str = ""
    entra_ciam_domain: str = ""  # just the subdomain, e.g. "mindgpt" for mindgpt.ciamlogin.com
    entra_api_client_id: str = ""  # the API app registration's client ID — expected JWT audience

    cosmos_endpoint: str = ""
    cosmos_database_name: str = "mindgpt"
    blob_endpoint: str = ""
    search_endpoint: str = ""
    content_safety_endpoint: str = ""
    language_endpoint: str = ""

    azure_openai_endpoint: str = ""
    azure_openai_chat_deployment: str = ""
    azure_openai_embedding_deployment: str = ""
    azure_openai_api_version: str = "2024-10-21"

    cors_allowed_origin: str = "http://localhost:5173"
    prompt_logging_enabled: bool = False
    # Interactive API docs (Swagger UI / ReDoc / OpenAPI schema) are OFF by default to reduce
    # recon surface in production (flagged by security/dast_probe.py). Turn on in local dev via
    # ENABLE_API_DOCS=true. See docs/SECURITY_VALIDATION.md §5.
    enable_api_docs: bool = False


settings = Settings()
