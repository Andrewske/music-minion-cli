"""
Bucket session API endpoints.

Provides CRUD operations for bucket-based playlist organization with emoji integration.
"""

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from ..queries import buckets as bucket_queries


router = APIRouter(prefix="/api/buckets", tags=["buckets"])


# === Pydantic Models ===


class CreateSessionBody(BaseModel):
    """Request body for creating/resuming a bucket session."""

    playlist_id: int


class CreateBucketBody(BaseModel):
    """Request body for creating a bucket."""

    name: str
    emoji_id: str | None = None


class UpdateBucketBody(BaseModel):
    """Request body for updating a bucket."""

    name: str | None = None
    emoji_id: str | None = None


class MoveBucketBody(BaseModel):
    """Request body for moving a bucket."""

    direction: str  # 'up' or 'down'


class ReorderBody(BaseModel):
    """Request body for reordering tracks within a bucket."""

    track_ids: list[int]


class BucketResponse(BaseModel):
    """Bucket representation for API responses."""

    id: str
    name: str
    emoji_id: str | None
    position: int
    track_ids: list[int]


class SessionResponse(BaseModel):
    """Session representation for API responses."""

    id: str
    playlist_id: int
    status: str
    buckets: list[BucketResponse]
    unassigned_track_ids: list[int]


class ShuffleResponse(BaseModel):
    """Response for shuffle operation."""

    track_ids: list[int]


class AssignResponse(BaseModel):
    """Response for track assignment."""

    bucket_id: str
    track_id: int
    position: int


# === Session Endpoints ===


@router.post("/sessions", response_model=SessionResponse)
async def create_or_resume_session(body: CreateSessionBody):
    """Create or resume session for playlist."""
    try:
        session = bucket_queries.get_or_create_session(body.playlist_id)
        if not session:
            raise HTTPException(
                status_code=404, detail=f"Playlist {body.playlist_id} not found"
            )
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create/resume session")
        raise HTTPException(
            status_code=500, detail=f"Failed to create/resume session: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get session with buckets and track assignments."""
    try:
        session = bucket_queries.get_session_with_data(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get session")
        raise HTTPException(status_code=500, detail=f"Failed to get session: {str(e)}")


@router.delete("/sessions/{session_id}")
async def discard_session_endpoint(session_id: str) -> dict[str, bool]:
    """Discard session (removes bucket emojis from tracks)."""
    try:
        success = bucket_queries.discard_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"discarded": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to discard session")
        raise HTTPException(
            status_code=500, detail=f"Failed to discard session: {str(e)}"
        )


@router.post("/sessions/{session_id}/apply")
async def apply_session_endpoint(session_id: str) -> dict[str, bool]:
    """Apply order to playlist."""
    try:
        success = bucket_queries.apply_session(session_id)
        if not success:
            raise HTTPException(
                status_code=404, detail="Session not found or not active"
            )
        return {"applied": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to apply session")
        raise HTTPException(
            status_code=500, detail=f"Failed to apply session: {str(e)}"
        )


# === Bucket Endpoints ===


@router.post("/sessions/{session_id}/buckets", response_model=BucketResponse)
async def create_bucket_endpoint(session_id: str, body: CreateBucketBody):
    """Create bucket."""
    try:
        # Verify session exists and is active
        session = bucket_queries.get_session_with_data(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session["status"] != "active":
            raise HTTPException(
                status_code=400,
                detail=f"Session is {session['status']}, cannot create buckets",
            )

        # Calculate next position
        next_position = len(session["buckets"])

        bucket = bucket_queries.create_bucket(
            session_id, body.name, body.emoji_id, next_position
        )
        return bucket
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create bucket")
        raise HTTPException(
            status_code=500, detail=f"Failed to create bucket: {str(e)}"
        )


@router.patch("/{bucket_id}", response_model=BucketResponse)
async def update_bucket_endpoint(bucket_id: str, body: UpdateBucketBody):
    """Update bucket (name, emoji)."""
    try:
        bucket = bucket_queries.update_bucket(bucket_id, body.name, body.emoji_id)
        if not bucket:
            raise HTTPException(status_code=404, detail="Bucket not found")
        return bucket
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update bucket")
        raise HTTPException(
            status_code=500, detail=f"Failed to update bucket: {str(e)}"
        )


@router.delete("/{bucket_id}")
async def delete_bucket_endpoint(bucket_id: str) -> dict[str, bool]:
    """Delete bucket."""
    try:
        success = bucket_queries.delete_bucket(bucket_id)
        if not success:
            raise HTTPException(status_code=404, detail="Bucket not found")
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete bucket")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete bucket: {str(e)}"
        )


@router.post("/{bucket_id}/move")
async def move_bucket_endpoint(bucket_id: str, body: MoveBucketBody) -> dict[str, bool]:
    """Move bucket up/down."""
    try:
        if body.direction not in ("up", "down"):
            raise HTTPException(
                status_code=400, detail="Direction must be 'up' or 'down'"
            )

        success = bucket_queries.move_bucket(bucket_id, body.direction)
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Cannot move bucket (not found or already at edge)",
            )
        return {"moved": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to move bucket")
        raise HTTPException(status_code=500, detail=f"Failed to move bucket: {str(e)}")


@router.post("/{bucket_id}/shuffle", response_model=ShuffleResponse)
async def shuffle_bucket_endpoint(bucket_id: str):
    """Randomize track order within bucket."""
    try:
        track_ids = bucket_queries.shuffle_bucket_tracks(bucket_id)
        if track_ids == []:
            # Could be empty bucket or not found - check which
            session_id = _get_session_id_for_bucket(bucket_id)
            if session_id is None:
                raise HTTPException(status_code=404, detail="Bucket not found")

        return {"track_ids": track_ids}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to shuffle bucket")
        raise HTTPException(
            status_code=500, detail=f"Failed to shuffle bucket: {str(e)}"
        )


def _get_session_id_for_bucket(bucket_id: str) -> str | None:
    """Helper to get session_id for a bucket."""
    from music_minion.core.database import get_db_connection

    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT session_id FROM buckets WHERE id = ?",
            (bucket_id,),
        )
        row = cursor.fetchone()
        return row["session_id"] if row else None


# === Track Assignment Endpoints ===


@router.post("/{bucket_id}/tracks/{track_id}", response_model=AssignResponse)
async def assign_track_endpoint(bucket_id: str, track_id: int):
    """Assign track to bucket."""
    try:
        result = bucket_queries.assign_track_to_bucket(bucket_id, track_id)
        if not result:
            raise HTTPException(status_code=404, detail="Bucket not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to assign track")
        raise HTTPException(status_code=500, detail=f"Failed to assign track: {str(e)}")


@router.delete("/{bucket_id}/tracks/{track_id}")
async def unassign_track_endpoint(bucket_id: str, track_id: int) -> dict[str, bool]:
    """Unassign track from bucket."""
    try:
        success = bucket_queries.unassign_track(bucket_id, track_id)
        if not success:
            raise HTTPException(
                status_code=404, detail="Track not in bucket or bucket not found"
            )
        return {"unassigned": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to unassign track")
        raise HTTPException(
            status_code=500, detail=f"Failed to unassign track: {str(e)}"
        )


@router.post("/{bucket_id}/tracks/reorder")
async def reorder_tracks_endpoint(bucket_id: str, body: ReorderBody) -> dict[str, bool]:
    """Reorder tracks within bucket."""
    try:
        success = bucket_queries.reorder_bucket_tracks(bucket_id, body.track_ids)
        if not success:
            raise HTTPException(status_code=404, detail="Bucket not found")
        return {"reordered": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to reorder tracks")
        raise HTTPException(
            status_code=500, detail=f"Failed to reorder tracks: {str(e)}"
        )
