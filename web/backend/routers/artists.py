"""Artists API endpoints — discovery artist stats."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from music_minion.core.database import get_db_connection
from web.backend.queries.artists import get_artist_stats

router = APIRouter(prefix="/api/artists", tags=["artists"])

_VALID_SOURCES = {"all", "soundcloud", "local", "following"}
_VALID_SORTS = {"name", "rank", "library", "reposts", "hit_rate", "noise", "last_loved"}


@router.get("")
async def list_artists(
    source: str = Query(default="all", description="Filter: all|soundcloud|local|following"),
    sort: str = Query(default="name", description="Sort: name|rank|library|reposts|hit_rate|noise|last_loved"),
) -> list[dict[str, Any]]:
    """Return all artist stats in a single CTE query.

    Supports source filtering and multiple sort options.
    Activity state is derived per-row from last_activity_at.
    """
    if source not in _VALID_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source '{source}'. Must be one of: {sorted(_VALID_SOURCES)}",
        )
    if sort not in _VALID_SORTS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort '{sort}'. Must be one of: {sorted(_VALID_SORTS)}",
        )

    try:
        with get_db_connection() as conn:
            return get_artist_stats(conn, source=source, sort=sort)
    except Exception as e:
        logger.exception(f"Failed to fetch artist stats: source={source} sort={sort}")
        raise HTTPException(status_code=500, detail=str(e))
