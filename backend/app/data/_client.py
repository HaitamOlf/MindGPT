"""Shared Cosmos container accessor. One place builds the managed-identity credential and
client (docs/ARCHITECTURE.md §7.3: `disableLocalAuth`, Entra RBAC only — never keys), so
every per-container store (conversations, profile, memory, wellness) connects identically.

Verified against the real azure-cosmos 4.17.1 SDK. Cached per container name so repeated
lookups reuse the same client.
"""

from __future__ import annotations

from functools import lru_cache

from azure.cosmos import ContainerProxy, CosmosClient
from azure.identity import DefaultAzureCredential

from app.core.config import settings


@lru_cache(maxsize=1)
def _client() -> CosmosClient:
    credential = DefaultAzureCredential(managed_identity_client_id=settings.azure_client_id or None)
    return CosmosClient(settings.cosmos_endpoint, credential)


@lru_cache(maxsize=None)
def get_container(name: str) -> ContainerProxy:
    database = _client().get_database_client(settings.cosmos_database_name)
    return database.get_container_client(name)
