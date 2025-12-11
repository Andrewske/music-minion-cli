from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse
from loguru import logger
import mimetypes
import json
from pathlib import Path
from typing import Optional
from ..waveform import has_cached_waveform, generate_waveform, get_waveform_path
from ..deps import get_db, get_config
from music_minion.core.config import Config

router = APIRouter()

# Add at top of file
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


@router.get("/tracks/{track_id}/stream")
async def stream_audio(
    track_id: int, db=Depends(get_db), config: Config = Depends(get_config)
):
    file_path = get_track_path(track_id, db)
    if not file_path:
        raise HTTPException(404, "Track not found")

    # SECURITY: Validate path within library
    from music_minion.core.path_security import validate_track_path

    validated = validate_track_path(file_path, config.music)
    if not validated:
        logger.warning(f"Blocked access outside library: {file_path}")
        raise HTTPException(403, "Access denied")

    logger.info(f"Streaming track {track_id}: {validated.name}")
    return FileResponse(validated, media_type=get_mime_type(validated))


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

        # Generate new waveform
        file_path = get_track_path(track_id, db)
        if not file_path:
            raise HTTPException(404, "Track not found")

        # SECURITY: Validate path within library
        from music_minion.core.path_security import validate_track_path

        validated = validate_track_path(file_path, config.music)
        if not validated:
            logger.warning(f"Blocked waveform access outside library: {file_path}")
            raise HTTPException(403, "Access denied")

        logger.info(f"Generating waveform for track {track_id}")
        waveform_data = generate_waveform(str(validated), track_id)

        return JSONResponse(waveform_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Waveform error for track {track_id}")
        raise HTTPException(500, f"Waveform generation failed: {str(e)}")


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
