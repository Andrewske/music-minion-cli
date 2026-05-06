from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from loguru import logger
import mimetypes
import json
from pathlib import Path
from typing import Optional
from ..waveform import has_cached_waveform, generate_waveform, get_waveform_path, get_waveform_cache_dir, fetch_soundcloud_waveform
from ..deps import get_db, get_config
from music_minion.core.config import Config

router = APIRouter()

AUDIO_MIME_TYPES: dict[str, str] = {
    ".opus": "audio/opus",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
}


def get_track_path(track_id: int, db_conn) -> Optional[Path]:
    """Pure function - query track path from database."""
    cursor = db_conn.execute("SELECT local_path FROM tracks WHERE id = ?", (track_id,))
    row = cursor.fetchone()

    # Handle NULL, empty string, and whitespace-only paths
    if not row or not row["local_path"] or not row["local_path"].strip():
        return None

    return Path(row["local_path"])


def get_mime_type(file_path: Path) -> str:
    """Pure function - deterministic MIME type detection."""
    mime = AUDIO_MIME_TYPES.get(file_path.suffix.lower())
    if mime:
        return mime
    guessed, _ = mimetypes.guess_type(str(file_path))
    return guessed or "application/octet-stream"


@router.get("/tracks/search")
async def search_tracks(q: str, limit: int = 20, db=Depends(get_db)) -> list[dict]:
    """Search local tracks for autocomplete.

    Uses simple LIKE query with case-insensitive matching.
    Returns tracks with local_path (true local files only).

    Args:
        q: Search query string
        limit: Maximum results to return (default 20)
        db: Database connection dependency

    Returns:
        List of dicts with id, title, artist, album
    """
    query = f"%{q}%"
    cursor = db.execute(
        """
        SELECT id, title, artist, album
        FROM tracks
        WHERE (title LIKE ? COLLATE NOCASE OR artist LIKE ? COLLATE NOCASE)
          AND local_path IS NOT NULL
        LIMIT ?
        """,
        (query, query, limit),
    )
    return [dict(row) for row in cursor.fetchall()]


def _mark_track_unavailable(db_conn, track_id: int, reason: str) -> None:
    """Stamp tracks.unavailable_at + reason so queue manager excludes the track."""
    db_conn.execute(
        "UPDATE tracks SET unavailable_at = CURRENT_TIMESTAMP, unavailable_reason = ?"
        " WHERE id = ?",
        (reason, track_id),
    )
    db_conn.commit()
    logger.warning(f"Marked track {track_id} unavailable: {reason}")


@router.get("/tracks/{track_id}/stream")
async def stream_audio(
    track_id: int, db=Depends(get_db), config: Config = Depends(get_config)
):
    # Prioritize local file if it exists (even for SoundCloud tracks that were downloaded)
    file_path = get_track_path(track_id, db)
    if file_path and file_path.exists():
        # SECURITY: Validate path within library
        from music_minion.core.path_security import validate_track_path

        validated = validate_track_path(file_path, config.music)
        if validated:
            logger.info(f"Streaming local file for track {track_id}: {validated.name}")
            return FileResponse(validated, media_type=get_mime_type(validated))
        else:
            logger.warning(f"Blocked access outside library: {file_path}")

    # Fallback to SoundCloud streaming for tracks without local files
    cursor = db.execute(
        "SELECT source, source_url, soundcloud_id, unavailable_at, unavailable_reason"
        " FROM tracks WHERE id = ?",
        (track_id,),
    )
    row = cursor.fetchone()
    if row and row["unavailable_at"]:
        # Already known dead - short-circuit so client can skip immediately
        raise HTTPException(
            410,
            f"Track unavailable ({row['unavailable_reason'] or 'unknown'})",
        )

    if row and row["source"] == "soundcloud" and (row["soundcloud_id"] or row["source_url"]):
        from web.backend.soundcloud_auth import get_web_provider_state
        from music_minion.domain.library.providers.soundcloud.api import resolve_stream_url as sc_resolve
        from music_minion.domain.library.providers.soundcloud.exceptions import (
            TrackUnavailableError,
        )

        state = get_web_provider_state()
        if state and state.authenticated and row["soundcloud_id"]:
            try:
                # Resolve to actual CDN URL for browser playback (~200ms)
                stream_url = sc_resolve(state, row["soundcloud_id"])
            except TrackUnavailableError as exc:
                _mark_track_unavailable(db, track_id, "soundcloud_gone")
                raise HTTPException(410, str(exc))
            if stream_url:
                logger.info(f"Resolved SC stream for track {track_id}")
                return RedirectResponse(stream_url)

        # Fallback: yt-dlp for unauthenticated or API failure (~2-3s)
        if row["source_url"]:
            from music_minion.domain.radio.stream_resolver import resolve_stream_url
            stream_url = resolve_stream_url(row["source_url"])
            if stream_url:
                logger.info(f"Resolved stream via yt-dlp for track {track_id}")
                return RedirectResponse(stream_url)
            # yt-dlp also failed → upstream is gone for both paths
            _mark_track_unavailable(db, track_id, "ytdlp_failed")
            raise HTTPException(410, "Track unavailable on upstream")

        raise HTTPException(503, "Failed to resolve stream URL")

    # No local file and not a SoundCloud track - track not found
    raise HTTPException(404, "Track not found or no streamable source")


@router.get("/tracks/{track_id}/waveform")
async def get_waveform(
    track_id: int, db=Depends(get_db), config: Config = Depends(get_config)
):
    try:
        if has_cached_waveform(track_id):
            # Use cached waveform
            cache_path = get_waveform_path(track_id)
            try:
                with open(cache_path) as f:
                    waveform_data = json.load(f)
                logger.debug(f"Waveform cache hit for track {track_id}")
                return JSONResponse(waveform_data)
            except json.JSONDecodeError:
                # Corrupted cache, regenerate
                pass

        # Check if it's a SoundCloud track
        cursor = db.execute(
            "SELECT source, soundcloud_id, duration FROM tracks WHERE id = ?",
            (track_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(404, "Track not found")

        # Prioritize local file for waveform generation
        file_path = get_track_path(track_id, db)
        if file_path:
            # SECURITY: Validate path within library
            from music_minion.core.path_security import validate_track_path

            validated = validate_track_path(file_path, config.music)
            if validated and validated.exists():
                logger.info(f"Generating waveform from local file for track {track_id}")
                waveform_data = generate_waveform(str(validated), track_id)
                return JSONResponse(waveform_data)

        # Fallback to SoundCloud API for streaming-only tracks
        if row["soundcloud_id"]:
            duration = row["duration"] or 0
            waveform_data = fetch_soundcloud_waveform(
                row["soundcloud_id"], track_id, duration
            )
            if waveform_data:
                logger.info(f"Fetched SoundCloud waveform for track {track_id}")
                return JSONResponse(waveform_data)

        raise HTTPException(404, "No waveform source available")

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Waveform error for track {track_id}")
        raise HTTPException(500, f"Waveform generation failed: {str(e)}")


@router.delete("/tracks/{track_id}/waveform")
async def delete_waveform_cache(track_id: int) -> dict[str, bool]:
    cache_path = get_waveform_path(track_id)
    if cache_path.exists():
        cache_path.unlink()
    return {"ok": True}


@router.post("/waveforms/purge-soundcloud")
async def purge_soundcloud_waveforms() -> dict[str, int]:
    cache_dir = get_waveform_cache_dir()
    count = 0
    for f in cache_dir.glob("*.json"):
        try:
            with open(f) as fh:
                data = json.load(fh)
            if data.get("source") == "soundcloud":
                f.unlink()
                count += 1
        except (json.JSONDecodeError, OSError):
            continue
    return {"purged": count}


@router.post("/tracks/{track_id}/archive")
async def archive_track(track_id: int):
    """Archive a track from comparisons."""
    try:
        # Import the database function for adding ratings
        from music_minion.core.database import add_rating

        # Archive the track by adding an 'archive' rating
        add_rating(track_id, "archive", "Archived from web UI comparison")

        logger.info(f"Track {track_id} archived successfully")
        return {"success": True, "message": "Track archived successfully"}

    except Exception as e:
        logger.exception(f"Failed to archive track {track_id}")
        raise HTTPException(
            status_code=500, detail=f"Failed to archive track: {str(e)}"
        )


@router.get("/folders")
async def list_folders(
    parent: Optional[str] = None, config: Config = Depends(get_config)
):
    """List subfolders of the library root or specified parent path."""
    try:
        if not config.music.library_paths:
            return {"root": "", "folders": []}

        # Determine the root path to list from
        if parent:
            # SECURITY: Validate parent path is within library boundaries
            from music_minion.core.path_security import is_path_within_library

            parent_path = Path(parent)
            if not is_path_within_library(parent_path, config.music.library_paths):
                logger.warning(
                    f"Blocked access to folder outside library: {parent_path}"
                )
                raise HTTPException(403, "Access denied")

            if not parent_path.exists() or not parent_path.is_dir():
                raise HTTPException(404, "Parent folder not found")

            music_root = parent_path
        else:
            # Use first library path as root
            music_root = Path(config.music.library_paths[0])
            if not music_root.exists():
                return {"root": str(music_root), "folders": []}

        all_folders = [d.name for d in music_root.iterdir() if d.is_dir()]
        # Sort: years (numeric) first descending, then alpha folders
        year_folders = sorted(
            [f for f in all_folders if f.isdigit()],
            reverse=True,
        )
        other_folders = sorted([f for f in all_folders if not f.isdigit()])
        folders = year_folders + other_folders

        return {
            "root": str(music_root),
            "folders": folders,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to list folders")
        raise HTTPException(status_code=500, detail=str(e))
