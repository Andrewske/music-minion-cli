"""DB side of the Tag review page: map ledger ids to tracks, refresh one track."""

from pathlib import Path

from loguru import logger

from music_minion.core.database import get_db_connection
from music_minion.domain.metadata_cleanup import apply as apply_mod
from music_minion.domain.sync.engine import get_file_mtime


def track_ids_by_path(paths: list[str]) -> dict[str, int]:
    """music-minion tracks.id per local_path (missing paths are left out)."""
    if not paths:
        return {}
    marks = ",".join("?" * len(paths))
    with get_db_connection() as conn:
        rows = conn.execute(
            f"SELECT id, local_path FROM tracks WHERE local_path IN ({marks})", paths
        ).fetchall()
    return {row["local_path"]: row["id"] for row in rows}


def refresh_track_from_file(path: Path) -> int | None:
    """Re-read title/artist/remixer from one file into its tracks row.

    These are the only tags the review writes, so a single-row UPDATE replaces
    a full /api/sync. The fields are set outright (no COALESCE) so a cleared
    remixer clears remix_artist. file_mtime is read after the write, so change
    detection won't re-import our own edit. Returns the track id, or None when
    the file has no tracks row yet (the next sync imports it).
    """
    tags = apply_mod.read_current(path)
    values = (
        tags["title"] or path.stem,
        tags["artist"] or None,
        tags["remixer"] or None,
    )
    with get_db_connection() as conn:
        row = conn.execute(
            "UPDATE tracks SET title = ?, artist = ?, remix_artist = ?, file_mtime = ?,"
            " updated_at = CURRENT_TIMESTAMP WHERE local_path = ? RETURNING id",
            (*values, get_file_mtime(str(path)), str(path)),
        ).fetchone()
        conn.commit()
    if row is None:
        logger.warning(f"Tag review: no tracks row for {path}; next sync imports it")
        return None
    return row["id"]
