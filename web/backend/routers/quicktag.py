"""Quick Tag router for dimension-based track voting."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Literal

from music_minion.core.database import get_db_connection

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


@router.post("/vote")
def submit_vote(request: VoteRequest) -> dict[str, bool]:
    """Upsert a vote for a track-dimension pair."""
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO track_dimension_votes (track_id, dimension_id, vote, voted_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (request.track_id, request.dimension_id, request.vote),
        )
        conn.commit()
    return {"success": True}


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
