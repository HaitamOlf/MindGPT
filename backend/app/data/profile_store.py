"""Per-user profile persistence (Cosmos `profile` container). Exactly one document per
user, with `id == userId`, so a profile read is a single point-read inside the caller's
own partition — a user can never read another user's profile (docs/ARCHITECTURE.md §7.3,
the same ownership-by-partition guarantee the conversation store uses).

Stores only the self-reported fields the account dashboard shows. `userId` always comes
from the validated JWT via the caller, never the request body.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.data._client import get_container

_CONTAINER_NAME = "profile"


def _container():
    return get_container(_CONTAINER_NAME)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Profile:
    user_id: str
    full_name: str
    date_of_birth: str
    country: str
    completed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.user_id,  # one profile per user; id == partition key value
            "userId": self.user_id,
            "fullName": self.full_name,
            "dateOfBirth": self.date_of_birth,
            "country": self.country,
            "completedAt": self.completed_at,
        }

    @staticmethod
    def from_dict(d: dict) -> "Profile":
        return Profile(
            user_id=d["userId"],
            full_name=d.get("fullName", ""),
            date_of_birth=d.get("dateOfBirth", ""),
            country=d.get("country", ""),
            completed_at=d.get("completedAt", ""),
        )


def get_profile(user_id: str) -> Profile | None:
    try:
        doc = _container().read_item(item=user_id, partition_key=user_id)
    except CosmosResourceNotFoundError:
        return None
    return Profile.from_dict(doc)


def upsert_profile(user_id: str, full_name: str, date_of_birth: str, country: str) -> Profile:
    profile = Profile(
        user_id=user_id,
        full_name=full_name,
        date_of_birth=date_of_birth,
        country=country,
        completed_at=_now_iso(),
    )
    _container().upsert_item(profile.to_dict())
    return profile
