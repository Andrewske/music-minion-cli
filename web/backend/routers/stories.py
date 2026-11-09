"""Stories page API: followed artists' recent activity, plus listened marks."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from web.backend.queries import feed as feed_queries
from web.backend.queries import stories as stories_queries

router = APIRouter(prefix="/api/stories", tags=["stories"])


class ListenedRequest(BaseModel):
    surface: str = Field(default="stories", max_length=64)


@router.get("")
def get_stories(
    days: int = Query(
        default=7, ge=stories_queries.MIN_DAYS, le=stories_queries.MAX_DAYS
    ),
) -> dict[str, Any]:
    """Artists with unheard tracks in the last `days`, newest activity first."""
    return stories_queries.get_stories(days)


@router.post("/{soundcloud_id}/listened")
def mark_listened(
    soundcloud_id: str, body: ListenedRequest | None = None
) -> dict[str, Any]:
    """Idempotent: re-marking keeps the first listen's time and surface."""
    if not feed_queries.track_is_known(soundcloud_id):
        raise HTTPException(
            status_code=404, detail=f"Unknown SoundCloud track {soundcloud_id}"
        )
    surface = (body or ListenedRequest()).surface
    stories_queries.mark_listened(soundcloud_id, surface)
    return {"soundcloud_id": soundcloud_id, "listened": True}
