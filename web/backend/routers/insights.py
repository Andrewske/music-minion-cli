"""Feed Insights: which keywords, genres, tags and reposters predict keeps."""

from typing import Any, Literal

from fastapi import APIRouter, Query

from web.backend.feed_insights import DEFAULT_MIN_COUNT
from web.backend.queries import insights as insight_queries

router = APIRouter(prefix="/api/insights", tags=["insights"])

Dimension = Literal[
    "keyword", "genre", "tag", "reposter", "uploader", "duration", "age"
]


@router.get("")
def get_insights(
    dimension: Dimension = "keyword",
    min_count: int = Query(default=DEFAULT_MIN_COUNT, ge=1, le=1000),
) -> dict[str, Any]:
    """Seen / keep % / lift per value, highest lift first."""
    return insight_queries.get_insights(dimension, min_count)


@router.get("/tracks")
def get_insight_tracks(
    dimension: Dimension,
    value: str = Query(min_length=1, max_length=500),
) -> dict[str, Any]:
    """The reviewed tracks behind one Insights row."""
    return insight_queries.get_insight_tracks(dimension, value)
