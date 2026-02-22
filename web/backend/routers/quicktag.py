"""Quick Tag router for dimension-based track voting."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Literal

from music_minion.core.database import get_db_connection
from ..queries.emojis import batch_fetch_track_emojis
from ..sync_manager import sync_manager

router = APIRouter()


class DimensionPair(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    id: str
    left_emoji: str
    right_emoji: str
    label: str
    description: str | None
    sort_order: int


class VoteRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    track_id: int
    dimension_id: str
    vote: Literal[-1, 0, 1]


class TrackDimensionVote(BaseModel):
    """Single vote for a track-dimension pair."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    dimension_id: str
    vote: int  # -1, 0, or 1
    voted_at: str


class VoteResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    success: bool
    emojis: list[str]


@router.get("/dimensions", response_model=list[DimensionPair])
def get_dimensions() -> list[DimensionPair]:
    """Return all dimension pairs ordered by sort_order."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT id, left_emoji, right_emoji, label, description, sort_order
            FROM dimension_pairs
            ORDER BY sort_order
            """
        )
        rows = cursor.fetchall()
        return [
            DimensionPair(
                id=row[0],
                left_emoji=row[1],
                right_emoji=row[2],
                label=row[3],
                description=row[4],
                sort_order=row[5],
            )
            for row in rows
        ]


@router.post("/vote", response_model=VoteResponse)
async def submit_vote(request: VoteRequest) -> VoteResponse:
    """Upsert a vote for a track-dimension pair."""
    with get_db_connection() as conn:
        # 1. Get dimension emojis (with validation)
        dim = conn.execute(
            "SELECT left_emoji, right_emoji FROM dimension_pairs WHERE id = ?",
            (request.dimension_id,)
        ).fetchone()

        if not dim:
            raise HTTPException(status_code=404, detail=f"Dimension '{request.dimension_id}' not found")

        # 2. Record vote (existing)
        conn.execute(
            "INSERT OR REPLACE INTO track_dimension_votes (track_id, dimension_id, vote, voted_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (request.track_id, request.dimension_id, request.vote),
        )

        # 3. Update track_emojis based on vote
        if request.vote != 0:
            winning_emoji = dim["left_emoji"] if request.vote == -1 else dim["right_emoji"]
            losing_emoji = dim["right_emoji"] if request.vote == -1 else dim["left_emoji"]

            conn.execute(
                "DELETE FROM track_emojis WHERE track_id = ? AND emoji_id = ?",
                (request.track_id, losing_emoji)
            )
            conn.execute(
                "INSERT OR IGNORE INTO track_emojis (track_id, emoji_id) VALUES (?, ?)",
                (request.track_id, winning_emoji)
            )
        else:
            conn.execute(
                "DELETE FROM track_emojis WHERE track_id = ? AND emoji_id IN (?, ?)",
                (request.track_id, dim["left_emoji"], dim["right_emoji"])
            )

        conn.commit()

        # 4. Get updated emojis
        emojis = batch_fetch_track_emojis([request.track_id], conn)
        emoji_list = emojis.get(request.track_id, [])

    # 5. Broadcast update via WebSocket (outside db context)
    await sync_manager.broadcast("track:emojis_updated", {
        "track_id": request.track_id,
        "emojis": emoji_list,
    })

    return VoteResponse(success=True, emojis=emoji_list)


@router.get("/tracks/{track_id}/votes", response_model=list[TrackDimensionVote])
def get_track_votes(track_id: int) -> list[TrackDimensionVote]:
    """Get all votes for a specific track."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT dimension_id, vote, voted_at
            FROM track_dimension_votes
            WHERE track_id = ?
            """,
            (track_id,),
        )
        rows = cursor.fetchall()
        return [
            TrackDimensionVote(
                dimension_id=row[0],
                vote=row[1],
                voted_at=row[2] if row[2] else "",
            )
            for row in rows
        ]
