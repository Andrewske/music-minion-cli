"""Artists API endpoints — discovery artist stats."""

from typing import Any

import requests as _requests
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from music_minion.core.database import get_db_connection
from music_minion.domain.library.providers.soundcloud.api import unfollow_user
from web.backend.queries.artists import (
    delete_match_override,
    get_artist_detail,
    get_artist_stats,
    get_pareto_artists,
    mark_artist_unfollowed,
    upsert_match_override,
)
from web.backend.soundcloud_auth import get_web_provider_state

router = APIRouter(prefix="/api/artists", tags=["artists"])

_VALID_SOURCES = {"all", "soundcloud", "local", "following"}
_VALID_SORTS = {"name", "rank", "library", "reposts", "hit_rate", "noise", "last_loved"}
_VALID_ACTIONS = {"merge", "split"}


class MatchOverrideRequest(BaseModel):
    discovery_artist_id: int
    local_artist_name: str
    action: str


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


@router.get("/pareto")
async def get_pareto() -> dict[str, Any]:
    """Return artists producing 80% of feed volume over the last 30 days.

    Uses a cumulative-sum window function ordered by event_count DESC.
    Includes each artist whose predecessor-cumulative was below 80%, so
    the smallest set of artists whose combined events reach 80% is returned.

    Returns:
        artists_producing_80pct: number of artists in the pareto set
        total_events: total feed events in the last 30 days
        threshold_ids: discovery_artist_id list, ordered by event_count DESC
    """
    try:
        with get_db_connection() as conn:
            return get_pareto_artists(conn)
    except Exception as e:
        logger.exception("Failed to compute pareto artists")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{discovery_artist_id}")
async def get_artist(discovery_artist_id: int) -> dict[str, Any]:
    """Return full detail for a single discovery artist.

    Includes:
    - artist: ArtistStats fields
    - recent_feed_events: last 50 feed events ordered by seen_at DESC
    - top_library_tracks: up to 20 local tracks by this artist ordered by play_count
    - match_overrides: all artist_match_overrides rows for this artist
    """
    try:
        with get_db_connection() as conn:
            detail = get_artist_detail(conn, discovery_artist_id)
        if detail is None:
            raise HTTPException(status_code=404, detail=f"Artist {discovery_artist_id} not found")
        return detail
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to fetch artist detail: id={discovery_artist_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{discovery_artist_id}/unfollow")
async def unfollow_artist(discovery_artist_id: int) -> dict[str, Any]:
    """Unfollow a discovery artist.

    If the artist has a soundcloud_user_id, calls the SC API to unfollow.
    SC 5xx / timeout → HTTP 503 with NO local state change.
    SC 403/404 (already unfollowed) → treated as success.

    On success:
    - Sets is_following = 0 on discovery_artists row (row is NOT deleted).
    - DELETEs all sc_feed_events for this artist.

    Returns:
        unfollowed: always True on success
        sc_called: whether SC API was called
        feed_events_deleted: number of feed events removed
    """
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id, soundcloud_user_id FROM discovery_artists WHERE id = ?",
            (discovery_artist_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Artist {discovery_artist_id} not found")

        sc_user_id: str | None = row["soundcloud_user_id"]

    # No SC user ID — local-only unfollow
    if not sc_user_id:
        with get_db_connection() as conn:
            feed_events_deleted = mark_artist_unfollowed(conn, discovery_artist_id)
            conn.commit()
        return {"unfollowed": True, "sc_called": False, "feed_events_deleted": feed_events_deleted}

    # SC unfollow — must succeed before mutating local state
    state = get_web_provider_state()
    if not state or not state.authenticated:
        raise HTTPException(status_code=401, detail="SoundCloud not authenticated")

    try:
        _state, _success = unfollow_user(state, sc_user_id)
    except _requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        logger.exception(
            f"SC unfollow failed for artist {discovery_artist_id} (sc_id={sc_user_id}): HTTP {status}"
        )
        raise HTTPException(status_code=503, detail="Unfollow failed, try again")
    except _requests.Timeout:
        logger.exception(f"SC unfollow timeout for artist {discovery_artist_id}")
        raise HTTPException(status_code=503, detail="Unfollow failed, try again")

    # SC call succeeded — update local state in single transaction
    with get_db_connection() as conn:
        feed_events_deleted = mark_artist_unfollowed(conn, discovery_artist_id)
        conn.commit()

    return {"unfollowed": True, "sc_called": True, "feed_events_deleted": feed_events_deleted}


@router.post("/match-override")
async def create_match_override(body: MatchOverrideRequest) -> dict[str, Any]:
    """Upsert an artist match override (merge or split).

    Normalizes local_artist_name using the same formula as tracks.artist_normalized.
    ON CONFLICT updates the action, so calling with the same artist pair is idempotent.
    """
    if body.action not in _VALID_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action '{body.action}'. Must be one of: {sorted(_VALID_ACTIONS)}",
        )

    try:
        with get_db_connection() as conn:
            # Validate discovery_artist_id exists
            row = conn.execute(
                "SELECT id FROM discovery_artists WHERE id = ?",
                (body.discovery_artist_id,),
            ).fetchone()
            if row is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Artist {body.discovery_artist_id} not found",
                )

            # Compute normalized name via SQL (mirrors tracks.artist_normalized)
            norm_row = conn.execute(
                "SELECT LOWER(TRIM(REPLACE(REPLACE(REPLACE(?, '.', ''), '!', ''), '?', '')))",
                (body.local_artist_name,),
            ).fetchone()
            normalized_name: str = norm_row[0] if norm_row else ""

            if not normalized_name:
                raise HTTPException(
                    status_code=400,
                    detail="local_artist_name is empty after normalization",
                )

            override_id = upsert_match_override(
                conn, body.discovery_artist_id, body.local_artist_name, body.action
            )
            conn.commit()

        return {
            "override_id": override_id,
            "discovery_artist_id": body.discovery_artist_id,
            "local_artist_name": normalized_name,
            "action": body.action,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            f"Failed to upsert match override: artist={body.discovery_artist_id} "
            f"name='{body.local_artist_name}' action={body.action}"
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/match-override/{override_id}")
async def remove_match_override(override_id: int) -> dict[str, Any]:
    """Delete a match override by id."""
    try:
        with get_db_connection() as conn:
            deleted = delete_match_override(conn, override_id)
            conn.commit()
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Override {override_id} not found")
        return {"deleted": True, "override_id": override_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to delete match override: id={override_id}")
        raise HTTPException(status_code=500, detail=str(e))
