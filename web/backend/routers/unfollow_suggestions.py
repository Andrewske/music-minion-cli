"""Followed SoundCloud accounts worth unfollowing, in sections."""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from music_minion.core.database import get_db_connection
from web.backend.artist_unfollow import unfollow_batch, unfollow_discovery_artist
from web.backend.queries import follow_suggestions as follow_queries
from web.backend.queries import unfollow_suggestions as queries
from web.backend.routers.follow_suggestions import SC_FOLLOWING_LIMIT

router = APIRouter(prefix="/api/unfollow-suggestions", tags=["unfollow-suggestions"])

MAX_BATCH = 10  # ~0.5-1s per SC unfollow: progress every few seconds


class BatchBody(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=MAX_BATCH)


@router.get("")
def get_unfollow_suggestions() -> dict[str, Any]:
    """Sections: redundant reposters, dormant, labels/channels, low yield."""
    with get_db_connection() as conn:
        sections = queries.compute_sections(conn)
        following = follow_queries.following_count(conn)
    return {
        "sections": sections,
        "following": {"count": following, "limit": SC_FOLLOWING_LIMIT},
        "generated_at": datetime.now(UTC).isoformat(),
    }


@router.post("/{discovery_artist_id}/keep")
def keep_account(discovery_artist_id: int) -> dict[str, bool]:
    """Never suggest this account again; untiered becomes tier C."""
    with get_db_connection() as conn:
        found = queries.keep(conn, discovery_artist_id)
    if not found:
        raise HTTPException(
            status_code=404, detail=f"Artist {discovery_artist_id} not found"
        )
    return {"ok": True}


@router.post("/{discovery_artist_id}/unfollow")
def unfollow_account(discovery_artist_id: int) -> dict[str, Any]:
    return unfollow_discovery_artist(discovery_artist_id)


@router.post("/unfollow-batch")
def unfollow_accounts(body: BatchBody) -> dict[str, Any]:
    """Unfollow up to MAX_BATCH in order; stops at the first service-wide SC error."""
    return unfollow_batch(body.ids)
