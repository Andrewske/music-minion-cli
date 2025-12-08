from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from loguru import logger
import mimetypes
import json
from pathlib import Path
from ..waveform import has_cached_waveform, generate_waveform, get_waveform_path

router = APIRouter()


@router.get("/tracks/{track_id}/stream")
async def stream_audio(track_id: int):
    """Stream audio file for a track."""
    from music_minion.core.database import get_db_connection

    try:
        with get_db_connection() as db:
            # Query track from database
            cursor = db.execute(
                "SELECT local_path FROM tracks WHERE id = ?", (track_id,)
            )
            row = cursor.fetchone()

            if row is None:
                raise HTTPException(status_code=404, detail="Track not found")

            file_path = Path(row["local_path"])

            if not file_path.exists():
                raise HTTPException(
                    status_code=404, detail=f"Audio file not found: {file_path}"
                )

            # Detect MIME type
            mime_type = None
            if file_path.suffix.lower() == ".opus":
                mime_type = "audio/opus"
            elif file_path.suffix.lower() == ".mp3":
                mime_type = "audio/mpeg"
            elif file_path.suffix.lower() == ".m4a":
                mime_type = "audio/mp4"
            else:
                mime_type, _ = mimetypes.guess_type(str(file_path))
                if mime_type is None:
                    mime_type = "application/octet-stream"

            logger.info(f"Streaming track {track_id}: {file_path.name}")

            return FileResponse(file_path, media_type=mime_type)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Stream error for track {track_id}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/tracks/{track_id}/waveform")
async def get_waveform(track_id: int):
    """Get pre-computed waveform data for a track."""
    from music_minion.core.database import get_db_connection

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
                # Corrupted cache, fall through to generation
                pass

        # Generate new waveform
        with get_db_connection() as db:
            cursor = db.execute(
                "SELECT local_path FROM tracks WHERE id = ?", (track_id,)
            )
            row = cursor.fetchone()

            if row is None:
                raise HTTPException(status_code=404, detail="Track not found")

            file_path = row["local_path"]

            if not Path(file_path).exists():
                raise HTTPException(
                    status_code=404, detail=f"Audio file not found: {file_path}"
                )

        logger.info(f"Generating waveform for track {track_id}")
        waveform_data = generate_waveform(file_path, track_id)

        return JSONResponse(waveform_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Waveform error for track {track_id}")
        raise HTTPException(
            status_code=500, detail=f"Waveform generation failed: {str(e)}"
        )


@router.post("/tracks/{track_id}/archive")
async def archive_track(track_id: int):
    """Archive a track from comparisons."""
    # TODO: Update track rating to 'archive' in database
    # For now, return a placeholder error
    raise HTTPException(status_code=501, detail="Track archiving not yet implemented")
