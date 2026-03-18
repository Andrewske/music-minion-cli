"""
Bucket session API endpoints.

Provides CRUD operations for bucket-based playlist organization with emoji integration.
"""

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from music_minion.core.database import get_db_connection
from web.backend.soundcloud_auth import get_web_provider_state
from music_minion.domain.library.providers.soundcloud.api import (
    add_track_to_playlist as sc_add_track,
    remove_track_from_playlist as sc_remove_track,
    get_playlist_tracks as sc_get_playlist_tracks,
)

from ..queries import buckets as bucket_queries
from .player import update_organizer_queue


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


class LinkBucketBody(BaseModel):
    """Request body for linking/unlinking a bucket to a playlist."""

    playlist_id: int | None  # None to unlink


class BucketResponse(BaseModel):
    """Bucket representation for API responses."""

    id: str
    name: str
    emoji_id: str | None
    position: int
    track_ids: list[int]
    linked_playlist_id: int | None
    linked_playlist_name: str | None
    linked_playlist_soundcloud_id: str | None = None


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


class SyncSoundCloudResponse(BaseModel):
    """Response for bidirectional SoundCloud sync."""

    pulled: int
    pushed_adds: int
    pushed_removals: int
    skipped: int
    errors: list[str]


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
    """Apply bucket order to playlist (keeps session active for continued editing)."""
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


@router.post("/sessions/{session_id}/finalize")
async def finalize_session_endpoint(session_id: str) -> dict[str, bool]:
    """Finalize session (marks as applied, closes organizing mode)."""
    try:
        success = bucket_queries.finalize_session(session_id)
        if not success:
            raise HTTPException(
                status_code=404, detail="Session not found or not active"
            )
        return {"finalized": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to finalize session")
        raise HTTPException(
            status_code=500, detail=f"Failed to finalize session: {str(e)}"
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


@router.post("/{bucket_id}/link")
async def link_bucket_endpoint(bucket_id: str, body: LinkBucketBody) -> dict[str, bool]:
    """Link/unlink bucket to playlist."""
    try:
        if body.playlist_id is None:
            success = bucket_queries.unlink_bucket(bucket_id)
        else:
            success = bucket_queries.link_bucket_to_playlist(bucket_id, body.playlist_id)
        if not success:
            raise HTTPException(status_code=404, detail="Bucket not found")
        return {"linked": body.playlist_id is not None}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to link/unlink bucket")
        raise HTTPException(
            status_code=500, detail=f"Failed to link/unlink bucket: {str(e)}"
        )


@router.get("/{bucket_id}/link")
async def get_bucket_link_endpoint(bucket_id: str) -> dict[str, int | None]:
    """Get current link status for bucket."""
    try:
        playlist_id = bucket_queries.get_bucket_link(bucket_id)
        return {"playlist_id": playlist_id}
    except Exception as e:
        logger.exception("Failed to get bucket link")
        raise HTTPException(
            status_code=500, detail=f"Failed to get bucket link: {str(e)}"
        )


@router.post("/{bucket_id}/sync-soundcloud", response_model=SyncSoundCloudResponse)
def sync_soundcloud_endpoint(bucket_id: str) -> SyncSoundCloudResponse:
    """Bidirectional sync: pull SC playlist tracks locally, push local changes to SC."""
    try:
        # 1. Resolve IDs
        with get_db_connection() as conn:
            row = conn.execute(
                """
                SELECT bpl.playlist_id, p.soundcloud_playlist_id
                FROM bucket_playlist_links bpl
                JOIN playlists p ON bpl.playlist_id = p.id
                WHERE bpl.bucket_id = ?
                """,
                (bucket_id,),
            ).fetchone()

        if not row:
            raise HTTPException(status_code=400, detail="Bucket is not linked to a playlist")

        linked_playlist_id: int = row["playlist_id"]
        sc_playlist_id: str | None = row["soundcloud_playlist_id"]

        if not sc_playlist_id:
            raise HTTPException(
                status_code=400,
                detail="Linked playlist has no SoundCloud ID",
            )

        # 2. Auth
        state = get_web_provider_state()
        if state is None:
            raise HTTPException(status_code=401, detail="SoundCloud not authenticated")

        pulled = 0
        pushed_adds = 0
        pushed_removals = 0
        skipped = 0
        errors: list[str] = []

        # 3. PULL phase
        state, remote_tracks, _ = sc_get_playlist_tracks(state, sc_playlist_id)
        remote_sc_ids: set[str] = set()

        with get_db_connection() as conn:
            # Get max position in local playlist
            max_pos_row = conn.execute(
                "SELECT COALESCE(MAX(position), -1) as max_pos FROM playlist_tracks WHERE playlist_id = ?",
                (linked_playlist_id,),
            ).fetchone()
            next_position: int = max_pos_row["max_pos"] + 1

            for sc_track_id, _metadata in remote_tracks:
                remote_sc_ids.add(sc_track_id)

                # Look up local track by soundcloud_id
                local_row = conn.execute(
                    "SELECT id FROM tracks WHERE soundcloud_id = ?",
                    (sc_track_id,),
                ).fetchone()

                if not local_row:
                    continue

                local_track_id: int = local_row["id"]

                # Check if already in local playlist
                exists = conn.execute(
                    "SELECT 1 FROM playlist_tracks WHERE playlist_id = ? AND track_id = ?",
                    (linked_playlist_id, local_track_id),
                ).fetchone()

                if not exists:
                    conn.execute(
                        "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
                        (linked_playlist_id, local_track_id, next_position),
                    )
                    next_position += 1
                    pulled += 1

            conn.commit()

        # 4. PUSH phase
        with get_db_connection() as conn:
            # Get local playlist tracks with SC IDs
            local_rows = conn.execute(
                """
                SELECT t.soundcloud_id
                FROM playlist_tracks pt
                JOIN tracks t ON pt.track_id = t.id
                WHERE pt.playlist_id = ?
                """,
                (linked_playlist_id,),
            ).fetchall()

        local_sc_ids: set[str] = set()
        for r in local_rows:
            if r["soundcloud_id"]:
                local_sc_ids.add(r["soundcloud_id"])
            else:
                skipped += 1

        # Additions: in local but not in remote
        additions = local_sc_ids - remote_sc_ids
        for sc_track_id in additions:
            state, success, error = sc_add_track(state, sc_playlist_id, sc_track_id)
            if success:
                pushed_adds += 1
            elif error:
                errors.append(error)

        # Removals: in remote but not in local
        removals = remote_sc_ids - local_sc_ids
        for sc_track_id in removals:
            state, success, error = sc_remove_track(state, sc_playlist_id, sc_track_id)
            if success:
                pushed_removals += 1
            elif error:
                errors.append(error)

        return SyncSoundCloudResponse(
            pulled=pulled,
            pushed_adds=pushed_adds,
            pushed_removals=pushed_removals,
            skipped=skipped,
            errors=errors,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to sync SoundCloud")
        raise HTTPException(
            status_code=500, detail=f"Failed to sync SoundCloud: {str(e)}"
        )


def _get_session_id_for_bucket(bucket_id: str) -> str | None:
    """Helper to get session_id for a bucket."""
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

        # Get session_id to update organizer queue if playing
        session_id = _get_session_id_for_bucket(bucket_id)
        if session_id:
            await update_organizer_queue(session_id)

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

        # Get session_id to update organizer queue if playing
        session_id = _get_session_id_for_bucket(bucket_id)
        if session_id:
            await update_organizer_queue(session_id)

        return {"unassigned": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to unassign track")
        raise HTTPException(
            status_code=500, detail=f"Failed to unassign track: {str(e)}"
        )


@router.delete("/sessions/{session_id}/buckets/{bucket_id}/tracks")
async def bulk_unassign_from_bucket(
    session_id: str,
    bucket_id: str
) -> dict:
    """Unassign all tracks from a bucket (empty the bucket)."""
    try:
        # Validate session exists and is active
        session = bucket_queries.get_session_with_data(session_id)
        if not session:
            raise HTTPException(404, f"Session {session_id} not found")
        if session["status"] != "active":
            raise HTTPException(400, f"Session is {session['status']}, cannot modify")

        # Validate bucket exists in session
        bucket = next((b for b in session["buckets"] if b["id"] == bucket_id), None)
        if not bucket:
            raise HTTPException(404, f"Bucket {bucket_id} not found in session")

        # Delete all assignments for this bucket
        with get_db_connection() as db_conn:
            cursor = db_conn.execute(
                "DELETE FROM bucket_tracks WHERE bucket_id = ?",
                (bucket_id,)
            )
            deleted_count = cursor.rowcount
            db_conn.commit()

        # Update queue if currently playing from this session
        await update_organizer_queue(session_id)

        return {
            "session_id": session_id,
            "bucket_id": bucket_id,
            "tracks_unassigned": deleted_count
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to bulk unassign tracks")
        raise HTTPException(
            status_code=500, detail=f"Failed to bulk unassign tracks: {str(e)}"
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
