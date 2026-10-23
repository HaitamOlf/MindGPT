from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Unauthenticated liveness/readiness probe — what Container Apps' ingress probe
    (infra/modules/build/container-apps.bicep) hits. Deliberately does not touch
    Cosmos/Search/etc: a dependency outage shouldn't flip the container's own readiness and
    trigger a restart loop.
    """
    return {"status": "ok"}
