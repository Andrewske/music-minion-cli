"""Trigger-driven staleness and change-only refresh for smart playlists.

Smart playlists store their matches in playlist_tracks. DB triggers (schema
v76) bump `library_state.version` whenever a track or emoji change could alter
membership, and null `playlists.materialized_version` when one playlist's
filters or skip list change. A playlist is stale when its
materialized_version differs from the library version.

The refresh only touches what changed: it inserts newly matching tracks,
deletes tracks that stopped matching, and fixes positions. Rows it deletes
are always rows it wrote (`playlist_tracks.source = 'smart'`); rows added by
any other writer are left alone.
"""

import sqlite3
from typing import NamedTuple

from loguru import logger

from music_minion.core.database import get_db_connection
from music_minion.domain.playlists.filters import matching_track_ids

SMART_SOURCE = "smart"


class RefreshResult(NamedTuple):
    """What one smart playlist refresh changed."""

    playlist_id: int
    inserted: int
    deleted: int
    moved: int
    track_count: int

    @property
    def changed(self) -> bool:
        return bool(self.inserted or self.deleted or self.moved)


class _Row(NamedTuple):
    row_id: int
    track_id: int
    position: int
    owned: bool


def library_version(conn: sqlite3.Connection) -> int:
    """Current library_state version (bumped by the staleness triggers)."""
    row = conn.execute("SELECT version FROM library_state WHERE id = 1").fetchone()
    return row[0] if row else 0


def stale_smart_playlist_ids(conn: sqlite3.Connection) -> list[int]:
    """IDs of smart playlists whose stored tracks may be out of date."""
    cursor = conn.execute(
        """
        SELECT p.id FROM playlists p
        WHERE p.type = 'smart'
          AND (p.materialized_version IS NULL
               OR p.materialized_version != (SELECT version FROM library_state WHERE id = 1))
        ORDER BY p.id
        """
    )
    return [row[0] for row in cursor.fetchall()]


def _is_stale(conn: sqlite3.Connection, playlist_id: int) -> bool:
    return playlist_id in stale_smart_playlist_ids(conn)


def _is_smart(conn: sqlite3.Connection, playlist_id: int) -> bool:
    row = conn.execute(
        "SELECT type FROM playlists WHERE id = ?", (playlist_id,)
    ).fetchone()
    return bool(row) and row[0] == "smart"


def _current_rows(conn: sqlite3.Connection, playlist_id: int) -> list[_Row]:
    cursor = conn.execute(
        "SELECT id, track_id, position, source FROM playlist_tracks"
        " WHERE playlist_id = ? ORDER BY position, id",
        (playlist_id,),
    )
    return [_Row(r[0], r[1], r[2], r[3] == SMART_SOURCE) for r in cursor.fetchall()]


def _final_order(matches: list[int], rows: list[_Row]) -> list[int]:
    """Matches in filter order, then kept foreign rows in their current order."""
    match_set = set(matches)
    foreign_tail = [
        r.track_id for r in rows if not r.owned and r.track_id not in match_set
    ]
    return [*matches, *foreign_tail]


def _plan_changes(
    matches: list[int], rows: list[_Row]
) -> tuple[list[int], list[tuple[int, int]], list[tuple[int, int]]]:
    """Return (row ids to delete, (track_id, pos) to insert, (pos, row id) to move).

    Ownership check: only rows with source='smart' are ever deleted.
    """
    match_set = set(matches)
    deletes = [r.row_id for r in rows if r.owned and r.track_id not in match_set]
    present = {
        r.track_id: r for r in rows if not (r.owned and r.track_id not in match_set)
    }
    positions = {tid: pos for pos, tid in enumerate(_final_order(matches, rows))}
    inserts = [(tid, positions[tid]) for tid in matches if tid not in present]
    moves = [
        (positions[r.track_id], r.row_id)
        for r in present.values()
        if r.position != positions[r.track_id]
    ]
    return deletes, inserts, moves


def _apply_changes(
    conn: sqlite3.Connection,
    playlist_id: int,
    plan: tuple[list[int], list[tuple[int, int]], list[tuple[int, int]]],
) -> None:
    deletes, inserts, moves = plan
    conn.executemany(
        "DELETE FROM playlist_tracks WHERE id = ? AND source = ?",
        [(row_id, SMART_SOURCE) for row_id in deletes],
    )
    conn.executemany("UPDATE playlist_tracks SET position = ? WHERE id = ?", moves)
    conn.executemany(
        "INSERT INTO playlist_tracks (playlist_id, track_id, position, added_at, source)"
        " VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)",
        [(playlist_id, tid, pos, SMART_SOURCE) for tid, pos in inserts],
    )


def _stamp(
    conn: sqlite3.Connection, playlist_id: int, version: int, result: RefreshResult
) -> None:
    """Record the version this refresh saw; touch updated_at only on change."""
    conn.execute(
        """
        UPDATE playlists SET
            materialized_version = ?,
            track_count = ?,
            updated_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE updated_at END
        WHERE id = ?
        """,
        (version, result.track_count, result.changed, playlist_id),
    )


def _refresh_locked(conn: sqlite3.Connection, playlist_id: int) -> RefreshResult:
    """Diff-refresh one playlist inside an already-open write transaction."""
    version = library_version(conn)
    rows = _current_rows(conn, playlist_id)
    plan = _plan_changes(matching_track_ids(conn, playlist_id), rows)
    _apply_changes(conn, playlist_id, plan)
    deletes, inserts, moves = plan
    result = RefreshResult(
        playlist_id,
        len(inserts),
        len(deletes),
        len(moves),
        len(rows) - len(deletes) + len(inserts),
    )
    _stamp(conn, playlist_id, version, result)
    return result


def refresh_smart_playlist(
    playlist_id: int, only_if_stale: bool = False, busy_ms: int | None = None
) -> RefreshResult | None:
    """Bring one smart playlist's stored tracks in line with its filters.

    Runs under BEGIN IMMEDIATE so no writer can change tracks between reading
    the version and stamping it. Returns None when skipped (fresh or not smart).
    busy_ms caps the wait for the write lock (default: the connection's 30s).
    """
    with get_db_connection() as conn:
        if busy_ms is not None:
            conn.execute(f"PRAGMA busy_timeout = {int(busy_ms)}")
        conn.execute("BEGIN IMMEDIATE")
        try:
            skip = not _is_smart(conn, playlist_id) or (
                only_if_stale and not _is_stale(conn, playlist_id)
            )
            if skip:
                conn.rollback()
                return None
            result = _refresh_locked(conn, playlist_id)
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            raise
    if result.changed:
        logger.info(f"Smart playlist {playlist_id} refreshed: {result}")
    return result


# Read-path refreshes give up quickly when another writer holds the lock;
# the caller serves the stored rows and the worker catches up later.
READ_BUSY_MS = 500


def refresh_playlist_if_stale(playlist_id: int) -> bool:
    """Refresh one playlist if it is a stale smart playlist. True if it changed.

    Called on the read path, so a failed or lock-busy refresh is logged and
    the caller reads the last stored tracks instead of erroring.
    """
    try:
        with get_db_connection() as conn:
            if not _is_stale(conn, playlist_id):
                return False
        result = refresh_smart_playlist(
            playlist_id, only_if_stale=True, busy_ms=READ_BUSY_MS
        )
    except sqlite3.Error:
        logger.exception(f"Smart playlist {playlist_id} refresh failed on read")
        return False
    return bool(result and result.changed)


def refresh_stale_smart_playlists(busy_ms: int | None = None) -> list[RefreshResult]:
    """Refresh every stale smart playlist. One failure doesn't stop the rest."""
    with get_db_connection() as conn:
        stale = stale_smart_playlist_ids(conn)
    results = []
    for playlist_id in stale:
        try:
            result = refresh_smart_playlist(
                playlist_id, only_if_stale=True, busy_ms=busy_ms
            )
        except sqlite3.Error:
            logger.exception(f"Smart playlist {playlist_id} refresh failed")
            continue
        if result:
            results.append(result)
    return results
