"""Daily wellness aggregates (Cosmos `wellness` container). One document per user per day
(`id == YYYY-MM-DD`), holding a rolling average of message sentiment for that day and the
sample count. Powers the dashboard's wellness trend.

Data minimization (docs/ARCHITECTURE.md §7.4): only the derived average is stored, never
the message text that produced it. Partitioned by `/userId`; reads are partition-scoped.
"""

from __future__ import annotations

from dataclasses import dataclass

from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.data._client import get_container

_CONTAINER_NAME = "wellness"


def _container():
    return get_container(_CONTAINER_NAME)


@dataclass
class WellnessDay:
    date: str  # YYYY-MM-DD, also the document id
    user_id: str
    average_sentiment: float  # [-1.0, 1.0]
    sample_count: int

    def to_dict(self) -> dict:
        return {
            "id": self.date,  # one doc per user per day; id == the date
            "userId": self.user_id,
            "date": self.date,
            "averageSentiment": self.average_sentiment,
            "sampleCount": self.sample_count,
        }

    @staticmethod
    def from_dict(d: dict) -> "WellnessDay":
        return WellnessDay(
            date=d["date"],
            user_id=d["userId"],
            average_sentiment=d.get("averageSentiment", 0.0),
            sample_count=d.get("sampleCount", 0),
        )


def list_wellness(user_id: str, since: str) -> list[WellnessDay]:
    """Daily points for the user on or after `since` (YYYY-MM-DD), oldest first. Scoped to
    the user's partition so it can only return that user's own data."""
    query = "SELECT * FROM c WHERE c.date >= @since ORDER BY c.date ASC"
    items = _container().query_items(
        query=query,
        parameters=[{"name": "@since", "value": since}],
        partition_key=user_id,
    )
    return [WellnessDay.from_dict(item) for item in items]


def record_sentiment(user_id: str, sentiment: float, day: str) -> WellnessDay:
    """Fold one sentiment sample into the user's aggregate for `day`, as a running mean so
    no per-message history is kept. Reads the existing day (if any), updates the average,
    and upserts."""
    try:
        existing = WellnessDay.from_dict(_container().read_item(item=day, partition_key=user_id))
    except CosmosResourceNotFoundError:
        existing = None

    if existing is None:
        updated = WellnessDay(date=day, user_id=user_id, average_sentiment=sentiment, sample_count=1)
    else:
        new_count = existing.sample_count + 1
        new_average = (existing.average_sentiment * existing.sample_count + sentiment) / new_count
        updated = WellnessDay(
            date=day,
            user_id=user_id,
            average_sentiment=round(new_average, 4),
            sample_count=new_count,
        )

    _container().upsert_item(updated.to_dict())
    return updated
