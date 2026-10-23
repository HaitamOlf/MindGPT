"""Wellness trend — the daily sentiment averages the dashboard charts. Read-only here;
the data points are produced as a side effect of chatting (app/routers/chat.py records a
sentiment sample per user message via app/analysis/sentiment.py). `userId` comes only from
the validated JWT and the query is partition-scoped.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from app.auth.dependency import get_current_user_id
from app.data.wellness_store import list_wellness

router = APIRouter(prefix="/wellness", tags=["wellness"])

_DEFAULT_DAYS = 366  # a bit over a year, enough for the dashboard's 12-month view
_MAX_DAYS = 400


class WellnessPoint(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    date: str
    average_sentiment: float = Field(..., alias="averageSentiment")


@router.get("", response_model=list[WellnessPoint])
def get(
    days: int = Query(default=_DEFAULT_DAYS, ge=1, le=_MAX_DAYS),
    user_id: str = Depends(get_current_user_id),
) -> list[WellnessPoint]:
    since = (datetime.now(timezone.utc) - timedelta(days=days - 1)).date().isoformat()
    return [
        WellnessPoint(date=day.date, average_sentiment=day.average_sentiment)
        for day in list_wellness(user_id, since)
    ]
