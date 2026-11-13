"""Genre API endpoints."""
import threading
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from music_minion.core.config import Config
from music_minion.core.database import get_db_connection
from music_minion.domain.library.metadata import write_metadata_to_file
from music_minion.domain.sync.engine import get_file_mtime, mtime_after_own_write

from ..deps import get_config
from ..queries.genres import (
    assign_genre_emoji_mutation,
    create_genre_mutation,
    delete_genre_mutation,
    get_all_genres_query,
    get_track_genres_query,
    primary_genre_display_query,
    record_written_genre_mutation,
    rename_genre_mutation,
    set_track_genres_mutation,
    validate_track_genres_query,
)

router = APIRouter(prefix="/api", tags=["genres"])

# Serializes genre saves (file write + DB update) so overlapping requests can't
# leave the file and DB disagreeing; write_metadata_to_file also uses a fixed
# <file>.tmp path. Saves are rare and single-user, so one lock is plenty.
_GENRE_SAVE_LOCK = threading.Lock()


class GenreNameRequest(BaseModel):
    name: str


class AssignEmojiRequest(BaseModel):
    emoji_id: str | None


class UpdateTrackGenresRequest(BaseModel):
    genre_ids: list[int]


@router.get("/genres")
def list_genres() -> list[dict]:
    return get_all_genres_query()


@router.post("/genres")
def create_genre(request: GenreNameRequest) -> dict:
    try:
        return create_genre_mutation(request.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/genres/{genre_id}")
def rename_genre(genre_id: int, request: GenreNameRequest) -> dict:
    return rename_genre_mutation(genre_id, request.name)


@router.put("/genres/{genre_id}/emoji")
def assign_emoji(genre_id: int, request: AssignEmojiRequest) -> dict:
    return assign_genre_emoji_mutation(genre_id, request.emoji_id)


@router.delete("/genres/{genre_id}")
def delete_genre(genre_id: int) -> dict:
    try:
        return delete_genre_mutation(genre_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tracks/{track_id}/genres")
def get_track_genres(track_id: int) -> list[dict]:
    return get_track_genres_query(track_id)


def _track_file(track_id: int, config: Config) -> Path | None:
    """The track's file inside the library, or None for tracks without one."""
    from music_minion.core.path_security import validate_track_path

    with get_db_connection() as conn:
        row = conn.execute("SELECT local_path FROM tracks WHERE id = ?", (track_id,)).fetchone()
    if not row or not (row["local_path"] or "").strip():
        return None
    path = Path(row["local_path"])
    if not path.exists():
        return None
    validated = validate_track_path(path, config.music)
    if not validated:
        logger.warning(f"Genre tag: skipped file outside library: {path}")
    return validated


def _stored_file_mtime(track_id: int) -> float | None:
    with get_db_connection() as conn:
        row = conn.execute("SELECT file_mtime FROM tracks WHERE id = ?", (track_id,)).fetchone()
    return row["file_mtime"] if row else None


def _write_genre_tag(track_id: int, path: Path, display: str) -> float | None:
    """Write the tag; return the file_mtime to store afterwards."""
    before = get_file_mtime(str(path))
    if not write_metadata_to_file(str(path), genre=display):
        raise HTTPException(
            status_code=500,
            detail=f"Couldn't write genre {display!r} to {path.name}; genres unchanged (see server log)",
        )
    logger.info(f"Genre tag for track {track_id} ({path.name}) -> {display!r}")
    return mtime_after_own_write(_stored_file_mtime(track_id), before, get_file_mtime(str(path)))


@router.put("/tracks/{track_id}/genres")
def update_track_genres(
    track_id: int,
    request: UpdateTrackGenresRequest,
    config: Annotated[Config, Depends(get_config)],
) -> list[dict]:
    """Set the track's genres; the primary one is also written to the file's genre
    tag (Serato reads it). Everything is validated and the file written before the
    DB changes, so a failed request changes nothing."""
    try:
        validate_track_genres_query(track_id, request.genre_ids)
        display = primary_genre_display_query(request.genre_ids)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    with _GENRE_SAVE_LOCK:
        path = _track_file(track_id, config)
        file_mtime = _write_genre_tag(track_id, path, display) if path else None
        genres = set_track_genres_mutation(track_id, request.genre_ids)
        record_written_genre_mutation(track_id, display, file_mtime)
    return genres
