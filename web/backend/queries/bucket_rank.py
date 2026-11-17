"""Organizer "Apply rating": turn a bucket's manual order into playlist ELO.

Writes only ``playlist_elo_ratings`` (never comparison history, which would
mark pairs as compared globally) plus one ``bucket_rank_applications`` row per
apply for undo. Ratings go to the session's playlist, not a linked playlist.
Undo is a stack: only the newest live application on a playlist can be undone.
"""

import json
import sqlite3
import uuid
from typing import Any

from loguru import logger

from music_minion.core.database import get_db_connection
from music_minion.domain.rating.bulk import DEFAULT_RATING, compute_rank_ratings

from .buckets import _begin_immediate, _session_playlist_id, _visible_bucket_track_ids

RATING_EPSILON = 1e-6


class RankConflictError(Exception):
    """The request no longer matches DB state (stale order, not newest, undone)."""


def _current_ratings(
    conn: sqlite3.Connection, playlist_id: int, track_ids: list[int]
) -> dict[int, sqlite3.Row]:
    """Existing playlist_elo_ratings rows for these tracks, keyed by track id."""
    placeholders = ",".join("?" * len(track_ids))
    rows = conn.execute(
        f"""
        SELECT track_id, rating, comparison_count FROM playlist_elo_ratings
        WHERE playlist_id = ? AND track_id IN ({placeholders})
        """,
        (playlist_id, *track_ids),
    ).fetchall()
    return {row["track_id"]: row for row in rows}


def _build_plan(conn: sqlite3.Connection, bucket_id: str) -> dict[str, Any]:
    """Compute new ratings for the bucket's visible order.

    Raises LookupError (no bucket) or ValueError (fewer than 2 visible tracks).
    """
    playlist_id = _session_playlist_id(conn, bucket_id)
    if playlist_id is None:
        raise LookupError(f"Bucket {bucket_id} not found")
    track_ids = _visible_bucket_track_ids(conn, bucket_id, playlist_id)
    if len(track_ids) < 2:
        raise ValueError(f"Bucket {bucket_id} has {len(track_ids)} visible tracks")
    existing = _current_ratings(conn, playlist_id, track_ids)
    new, method = compute_rank_ratings(
        track_ids, {tid: row["rating"] for tid, row in existing.items()}
    )
    rows = [_snapshot_entry(tid, existing.get(tid), new[tid]) for tid in track_ids]
    return {
        "playlist_id": playlist_id,
        "track_ids": track_ids,
        "method": method,
        "rows": rows,
    }


def _snapshot_entry(track_id: int, row: sqlite3.Row | None, after: float) -> dict:
    """One track's before/after state; had_row says whether apply creates the row."""
    return {
        "track_id": track_id,
        "before": row["rating"] if row else None,
        "after": after,
        "had_row": row is not None,
        "comparison_count": row["comparison_count"] if row else 0,
    }


def _public(plan: dict[str, Any]) -> dict[str, Any]:
    """API shape: track order, method, and rows with before (1500 if unrated)."""
    rows = [
        {
            "track_id": r["track_id"],
            "before": DEFAULT_RATING if r["before"] is None else r["before"],
            "after": r["after"],
        }
        for r in plan["rows"]
    ]
    return {"track_ids": plan["track_ids"], "method": plan["method"], "rows": rows}


def preview_bucket_rating(bucket_id: str) -> dict[str, Any]:
    """What apply would write, without writing."""
    with get_db_connection() as conn:
        return _public(_build_plan(conn, bucket_id))


def apply_bucket_rating(
    bucket_id: str, expected_track_ids: list[int]
) -> dict[str, Any]:
    """Write the bucket's rank ratings in one transaction.

    expected_track_ids is the order the user previewed; a mismatch (a reorder or
    membership change landed since) raises RankConflictError with no writes.
    An order that changes no rating writes nothing and returns application_id
    None, so a no-op never becomes the newest entry on the undo stack.
    """
    with get_db_connection() as conn:
        _begin_immediate(conn)
        plan = _build_plan(conn, bucket_id)
        if plan["track_ids"] != expected_track_ids:
            raise RankConflictError(f"Bucket {bucket_id} order changed since preview")
        if _is_noop(plan):
            return {"application_id": None, **_public(plan)}
        application_id = _insert_application(conn, bucket_id, plan)
        _write_ratings(conn, plan)
        conn.commit()
    logger.info(
        f"Applied {plan['method']} rating to {len(plan['rows'])} tracks "
        f"(bucket {bucket_id}, playlist {plan['playlist_id']})"
    )
    return {"application_id": application_id, **_public(plan)}


def _is_noop(plan: dict[str, Any]) -> bool:
    """True when every track already has its target rating (unrated = 1500)."""
    return all(
        abs(r["after"] - (DEFAULT_RATING if r["before"] is None else r["before"]))
        < RATING_EPSILON
        for r in plan["rows"]
    )


def _write_ratings(conn: sqlite3.Connection, plan: dict[str, Any]) -> None:
    conn.executemany(
        """
        INSERT INTO playlist_elo_ratings (track_id, playlist_id, rating)
        VALUES (?, ?, ?)
        ON CONFLICT(track_id, playlist_id) DO UPDATE SET
            rating = excluded.rating, updated_at = CURRENT_TIMESTAMP
        """,
        [(r["track_id"], plan["playlist_id"], r["after"]) for r in plan["rows"]],
    )


def _insert_application(
    conn: sqlite3.Connection, bucket_id: str, plan: dict[str, Any]
) -> str:
    application_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO bucket_rank_applications (id, bucket_id, playlist_id, method, snapshot)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            application_id,
            bucket_id,
            plan["playlist_id"],
            plan["method"],
            json.dumps(plan["rows"]),
        ),
    )
    return application_id


def _undo_actions(
    snapshot: list[dict], current: dict[int, sqlite3.Row]
) -> tuple[list[tuple[float, int]], list[int], int]:
    """Split snapshot into (restores, deletes, skipped).

    A track is untouched since apply only if its rating still equals `after`
    and its comparison_count is unchanged; anything else is skipped.
    """
    restores, deletes, skipped = [], [], 0
    for entry in snapshot:
        row = current.get(entry["track_id"])
        if not _unchanged_since_apply(entry, row):
            skipped += 1
        elif entry["had_row"]:
            restores.append((entry["before"], entry["track_id"]))
        else:
            deletes.append(entry["track_id"])
    return restores, deletes, skipped


def _unchanged_since_apply(entry: dict, row: sqlite3.Row | None) -> bool:
    return (
        row is not None
        and abs(row["rating"] - entry["after"]) < RATING_EPSILON
        and row["comparison_count"] == entry["comparison_count"]
    )


def _load_undoable(conn: sqlite3.Connection, application_id: str) -> sqlite3.Row:
    """The application row, if it is the newest live one on its playlist."""
    app = conn.execute(
        "SELECT * FROM bucket_rank_applications WHERE id = ?", (application_id,)
    ).fetchone()
    if app is None:
        raise LookupError(f"Rating application {application_id} not found")
    if app["undone_at"] is not None:
        raise RankConflictError(f"Rating application {application_id} already undone")
    newest = conn.execute(
        """
        SELECT id FROM bucket_rank_applications
        WHERE playlist_id = ? AND undone_at IS NULL
        ORDER BY rowid DESC LIMIT 1
        """,
        (app["playlist_id"],),
    ).fetchone()
    if newest["id"] != application_id:
        raise RankConflictError(
            "A newer rating was applied to this playlist; undo that first"
        )
    return app


def _write_undo(
    conn: sqlite3.Connection,
    application_id: str,
    playlist_id: int,
    restores: list[tuple[float, int]],
    deletes: list[int],
) -> None:
    """Restore old ratings, drop rows apply created, mark the application undone."""
    conn.executemany(
        """
        UPDATE playlist_elo_ratings SET rating = ?, updated_at = CURRENT_TIMESTAMP
        WHERE track_id = ? AND playlist_id = ?
        """,
        [(before, tid, playlist_id) for before, tid in restores],
    )
    conn.executemany(
        "DELETE FROM playlist_elo_ratings WHERE track_id = ? AND playlist_id = ?",
        [(tid, playlist_id) for tid in deletes],
    )
    conn.execute(
        "UPDATE bucket_rank_applications SET undone_at = CURRENT_TIMESTAMP WHERE id = ?",
        (application_id,),
    )


def undo_bucket_rating(application_id: str) -> dict[str, int]:
    """Restore pre-apply ratings for tracks untouched since. Returns counts."""
    with get_db_connection() as conn:
        _begin_immediate(conn)
        app = _load_undoable(conn, application_id)
        playlist_id = app["playlist_id"]
        snapshot = json.loads(app["snapshot"])
        current = _current_ratings(conn, playlist_id, [e["track_id"] for e in snapshot])
        restores, deletes, skipped = _undo_actions(snapshot, current)
        _write_undo(conn, application_id, playlist_id, restores, deletes)
        conn.commit()
    restored = len(restores) + len(deletes)
    logger.info(
        f"Undid rating application {application_id}: {restored} restored, {skipped} skipped"
    )
    return {"restored": restored, "skipped": skipped}
