"""Canonical queries for the deduplicated SoundCloud releases/reposts feed."""

import json
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from loguru import logger

from music_minion.core.database import get_db_connection

Decision = Literal["keep", "nope", "hide"]
FeedSource = Literal["all", "releases", "reposts"]

DECISIONS: tuple[str, ...] = ("keep", "nope", "hide")
FEED_SOURCES: tuple[str, ...] = ("all", "releases", "reposts")


def _utc_iso(column: str) -> str:
    """SQL that renders any stored timestamp as 'YYYY-MM-DDTHH:MM:SSZ'.

    Sources disagree on format: uploads store ISO ('2026-07-01T00:00:00+00:00'),
    SQLite defaults store '2026-07-01 00:00:00', and exact repost times keep
    SoundCloud's raw '2026/07/01 00:00:00 +0000'. Raw string comparison would
    order by separator, so every event time is normalized before ordering and
    keyset comparison. All stored values are UTC.
    """
    return f"strftime('%Y-%m-%dT%H:%M:%SZ', substr(replace({column}, '/', '-'), 1, 19))"


def _validate_decision(decision: str) -> None:
    if decision not in DECISIONS:
        raise ValueError(f"Invalid decision {decision!r}; valid values are {DECISIONS}")


def _validate_source(source: str) -> None:
    if source not in FEED_SOURCES:
        raise ValueError(
            f"Invalid feed source {source!r}; valid values are {FEED_SOURCES}"
        )


def _decision_to_legacy_status(decision: str) -> str:
    return {"keep": "liked", "nope": "dismissed", "hide": "hidden"}[decision]


def _row_to_artist(row: Any) -> dict[str, Any]:
    return {
        "id": row["uploader_artist_id"],
        "soundcloud_id": row["uploader_soundcloud_id"],
        "display_name": row["uploader_display_name"],
        "slug": row["uploader_slug"],
        "avatar_url": row["uploader_avatar_url"],
        "ranking": row["uploader_ranking"],
        "in_top_200": bool(
            row["uploader_ranking"] is not None and row["uploader_ranking"] <= 200
        ),
        "in_library": bool(row["artist_in_library"]),
    }


def _legacy_status(decision: Optional[str]) -> str:
    if decision is None:
        return "visible"
    return _decision_to_legacy_status(decision)


def _row_to_feed_item(row: Any) -> dict[str, Any]:
    sources = []
    if row["has_release"]:
        sources.append("release")
    if row["has_repost"]:
        sources.append("repost")
    current_decision = row["current_decision"]
    uploader = _row_to_artist(row)
    return {
        "id": row["soundcloud_id"],
        "soundcloud_id": row["soundcloud_id"],
        "local_track_id": row["local_track_id"],
        "title": row["title"],
        "artwork_url": row["artwork_url"],
        "permalink_url": row["permalink_url"],
        "duration_ms": row["duration_ms"] or 0,
        "genre": row["genre"],
        "access": row["access"],
        "event_at": row["event_at"],
        "uploaded_at": row["uploaded_at"],
        "released_at": row["released_at"],
        "sources": sources,
        "uploader_soundcloud_id": row["uploader_soundcloud_id"],
        "uploader": uploader,
        "artist": uploader,
        "status": _legacy_status(current_decision),
        "current_decision": current_decision,
        "decided_at": row["decided_at"],
        "in_likes": bool(row["in_likes"]),
        "in_playlists": bool(row["in_playlists"]),
        "best_reposter_rank": row["best_reposter_rank"],
        "reposter_count": row["reposter_count"] or 0,
        "reposters": [],
        "action_state": {"like": None, "monthly_playlist": None, "error": None},
        # Stable extension points for the production scorer (#62).
        "keep_probability": None,
        "prediction_model_version": None,
        "prediction_explanation": None,
    }


def _attach_reposters(
    conn: Any, items: list[dict[str, Any]], max_rank: Optional[int]
) -> None:
    if not items:
        return
    ids = [item["soundcloud_id"] for item in items]
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"""
        SELECT dt.soundcloud_id, da.id, da.soundcloud_user_id, da.display_name,
               da.slug, da.avatar_url, da.ranking,
               COALESCE({_utc_iso("dtr.reposted_at")}, {_utc_iso("dtr.seen_at")})
                   AS reposted_at,
               dtr.repost_time_precision
        FROM discovery_tracks dt
        JOIN discovery_track_reposters dtr ON dtr.discovery_track_id = dt.id
        JOIN discovery_artists da ON da.id = dtr.discovery_artist_id
        WHERE dt.soundcloud_id IN ({placeholders})
          AND da.is_following = 1
          AND (? IS NULL OR da.ranking <= ?)
        ORDER BY dt.soundcloud_id, da.ranking IS NULL, da.ranking, da.id
        """,
        [*ids, max_rank, max_rank],
    ).fetchall()
    by_id = {sc_id: [] for sc_id in ids}
    for row in rows:
        by_id[row["soundcloud_id"]].append(
            {
                "id": row["id"],
                "soundcloud_id": row["soundcloud_user_id"],
                "display_name": row["display_name"],
                "slug": row["slug"],
                "avatar_url": row["avatar_url"],
                "ranking": row["ranking"],
                "reposted_at": row["reposted_at"],
                "repost_time_precision": row["repost_time_precision"],
            }
        )
    for item in items:
        item["reposters"] = by_id[item["soundcloud_id"]]


def _attach_action_states(conn: Any, items: list[dict[str, Any]]) -> None:
    if not items:
        return
    ids = [item["soundcloud_id"] for item in items]
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"""
        SELECT soundcloud_id, action_type, status, last_error, created_at, id
        FROM sc_feed_action_jobs
        WHERE soundcloud_id IN ({placeholders})
        ORDER BY created_at, id
        """,
        ids,
    ).fetchall()
    states = {
        sc_id: {"like": None, "monthly_playlist": None, "error": None} for sc_id in ids
    }
    for row in rows:
        state = states[row["soundcloud_id"]]
        state[row["action_type"]] = row["status"]
        if row["last_error"]:
            state["error"] = row["last_error"]
    for item in items:
        item["action_state"] = states[item["soundcloud_id"]]


def get_feed_page(
    limit: int = 30,
    cursor_event_at: Optional[str] = None,
    cursor_soundcloud_id: Optional[str] = None,
    source: FeedSource = "all",
    max_rank: Optional[int] = None,
    in_library: bool = False,
    show_hidden: bool = False,
    top200: bool = False,
) -> list[dict[str, Any]]:
    """Fetch one deduplicated page; filters are applied before keyset paging.

    Cursor is the (event_at, soundcloud_id) of the previous page's last item.
    Rows inserted by a sync mid-scroll land above the cursor, so later pages
    never shift. `top200` is shorthand for max_rank=200.
    """
    _validate_source(source)
    limit = max(1, min(limit, 100))
    if top200 and max_rank is None:
        max_rank = 200
    if max_rank is not None and max_rank < 1:
        raise ValueError("max_rank must be at least 1")

    params = {
        "max_rank": max_rank,
        "include_releases": int(source in ("all", "releases")),
        "include_reposts": int(source in ("all", "reposts")),
        "cursor_event_at": cursor_event_at,
        "cursor_soundcloud_id": cursor_soundcloud_id or "",
        "show_hidden": int(show_hidden),
        "in_library": int(in_library),
        "limit": limit,
    }
    with get_db_connection() as conn:
        rows = conn.execute(
            f"""
            WITH release_events AS (
                SELECT u.soundcloud_id, u.local_track_id, u.title,
                       u.artwork_url, u.permalink_url, u.duration_ms, u.genre,
                       u.access, u.uploaded_at,
                       COALESCE(u.released_at, u.uploaded_at) AS released_at,
                       {_utc_iso("u.uploaded_at")} AS event_at,
                       da.id AS uploader_artist_id,
                       COALESCE(u.uploader_soundcloud_id, da.soundcloud_user_id)
                           AS uploader_soundcloud_id,
                       da.display_name AS uploader_display_name,
                       da.slug AS uploader_slug,
                       da.avatar_url AS uploader_avatar_url,
                       da.ranking AS uploader_ranking
                FROM sc_artist_uploads u
                JOIN discovery_artists da ON da.id = u.discovery_artist_id
                WHERE :include_releases = 1 AND da.is_following = 1
                  AND (:max_rank IS NULL OR da.ranking <= :max_rank)
                  AND (u.access IS NULL OR u.access = 'playable')
            ),
            repost_events AS (
                SELECT dt.soundcloud_id, dt.local_track_id, dt.title,
                       dt.artwork_url, dt.permalink_url, dt.duration_ms, dt.genre,
                       dt.access, dt.uploaded_at, dt.released_at,
                       MAX(COALESCE({_utc_iso("dtr.reposted_at")},
                                    {_utc_iso("dtr.seen_at")},
                                    {_utc_iso("dt.first_seen")})) AS event_at,
                       uda.id AS uploader_artist_id,
                       dt.uploader_soundcloud_id,
                       COALESCE(uda.display_name, dt.artist_name) AS uploader_display_name,
                       uda.slug AS uploader_slug,
                       uda.avatar_url AS uploader_avatar_url,
                       uda.ranking AS uploader_ranking,
                       MIN(da.ranking) AS best_reposter_rank,
                       COUNT(DISTINCT da.id) AS reposter_count
                FROM discovery_tracks dt
                JOIN discovery_track_reposters dtr ON dtr.discovery_track_id = dt.id
                JOIN discovery_artists da
                  ON da.id = dtr.discovery_artist_id AND da.is_following = 1
                LEFT JOIN discovery_artists uda
                  ON uda.soundcloud_user_id = dt.uploader_soundcloud_id
                WHERE :include_reposts = 1
                  AND (:max_rank IS NULL OR da.ranking <= :max_rank)
                  AND (dt.access IS NULL OR dt.access = 'playable')
                GROUP BY dt.id
            ),
            eligible_ids AS (
                SELECT soundcloud_id FROM release_events
                UNION SELECT soundcloud_id FROM repost_events
            ),
            combined AS (
                SELECT ids.soundcloud_id,
                       COALESCE(r.local_track_id, rp.local_track_id) AS local_track_id,
                       COALESCE(r.title, rp.title) AS title,
                       COALESCE(r.artwork_url, rp.artwork_url) AS artwork_url,
                       COALESCE(r.permalink_url, rp.permalink_url) AS permalink_url,
                       COALESCE(r.duration_ms, rp.duration_ms, 0) AS duration_ms,
                       COALESCE(r.genre, rp.genre) AS genre,
                       COALESCE(r.access, rp.access) AS access,
                       r.uploaded_at,
                       COALESCE(r.released_at, rp.released_at, rp.uploaded_at) AS released_at,
                       CASE
                           WHEN r.event_at IS NULL THEN rp.event_at
                           WHEN rp.event_at IS NULL THEN r.event_at
                           WHEN r.event_at >= rp.event_at THEN r.event_at
                           ELSE rp.event_at
                       END AS event_at,
                       COALESCE(r.uploader_artist_id, rp.uploader_artist_id)
                           AS uploader_artist_id,
                       COALESCE(r.uploader_soundcloud_id, rp.uploader_soundcloud_id)
                           AS uploader_soundcloud_id,
                       COALESCE(r.uploader_display_name, rp.uploader_display_name)
                           AS uploader_display_name,
                       COALESCE(r.uploader_slug, rp.uploader_slug) AS uploader_slug,
                       COALESCE(r.uploader_avatar_url, rp.uploader_avatar_url)
                           AS uploader_avatar_url,
                       COALESCE(r.uploader_ranking, rp.uploader_ranking)
                           AS uploader_ranking,
                       CASE WHEN r.soundcloud_id IS NULL THEN 0 ELSE 1 END AS has_release,
                       CASE WHEN rp.soundcloud_id IS NULL THEN 0 ELSE 1 END AS has_repost,
                       rp.best_reposter_rank, COALESCE(rp.reposter_count, 0) AS reposter_count
                FROM eligible_ids ids
                LEFT JOIN release_events r ON r.soundcloud_id = ids.soundcloud_id
                LEFT JOIN repost_events rp ON rp.soundcloud_id = ids.soundcloud_id
            )
            SELECT c.*, d.decision AS current_decision, d.decided_at,
                   EXISTS(
                       SELECT 1 FROM tracks t
                       WHERE t.artist_normalized = LOWER(TRIM(COALESCE(c.uploader_display_name, '')))
                         AND t.local_path IS NOT NULL
                   ) AS artist_in_library,
                   EXISTS(
                       SELECT 1 FROM tracks t JOIN ratings rt ON rt.track_id = t.id
                       WHERE t.source = 'soundcloud' AND t.soundcloud_id = c.soundcloud_id
                         AND rt.rating_type = 'like' AND rt.source = 'soundcloud'
                   ) AS in_likes,
                   EXISTS(
                       SELECT 1 FROM tracks t JOIN playlist_tracks pt ON pt.track_id = t.id
                       WHERE t.source = 'soundcloud' AND t.soundcloud_id = c.soundcloud_id
                   ) AS in_playlists
            FROM combined c
            LEFT JOIN sc_track_decisions d
              ON d.soundcloud_id = c.soundcloud_id AND d.is_current = 1
            WHERE (:show_hidden = 1 OR d.decision IS NULL OR d.decision = 'keep')
              AND (:in_library = 0 OR EXISTS(
                    SELECT 1 FROM tracks t
                    WHERE t.artist_normalized = LOWER(TRIM(COALESCE(c.uploader_display_name, '')))
                      AND t.local_path IS NOT NULL
              ))
              AND (:cursor_event_at IS NULL OR c.event_at < :cursor_event_at
                   OR (c.event_at = :cursor_event_at
                       AND c.soundcloud_id < :cursor_soundcloud_id))
            ORDER BY c.event_at DESC, c.soundcloud_id DESC LIMIT :limit
            """,
            params,
        ).fetchall()
        items = [_row_to_feed_item(row) for row in rows]
        _attach_reposters(conn, items, max_rank)
        _attach_action_states(conn, items)
    return items


def get_feed_track(soundcloud_id: str) -> Optional[dict[str, Any]]:
    """Return the best available metadata for one ingested SoundCloud track."""
    with get_db_connection() as conn:
        row = conn.execute(
            """SELECT soundcloud_id, local_track_id, title, artist_name,
                   duration_ms, genre, artwork_url, permalink_url
            FROM discovery_tracks WHERE soundcloud_id = ?""",
            (soundcloud_id,),
        ).fetchone()
        if row:
            return dict(row)
        row = conn.execute(
            """SELECT u.soundcloud_id, u.local_track_id, u.title,
                   da.display_name AS artist_name, u.duration_ms, u.genre,
                   u.artwork_url, u.permalink_url
            FROM sc_artist_uploads u
            JOIN discovery_artists da ON da.id = u.discovery_artist_id
            WHERE u.soundcloud_id = ?""",
            (soundcloud_id,),
        ).fetchone()
    return dict(row) if row else None


def materialize_feed_track(soundcloud_id: str) -> Optional[int]:
    """Create one streaming-only library row on first play/keep."""
    metadata = get_feed_track(soundcloud_id)
    if metadata is None:
        return None
    with get_db_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM tracks WHERE soundcloud_id = ? ORDER BY source = 'soundcloud' DESC LIMIT 1",
            (soundcloud_id,),
        ).fetchone()
        if existing:
            track_id = existing["id"]
        else:
            cursor = conn.execute(
                """INSERT INTO tracks
                    (soundcloud_id, source_url, title, artist, duration, genre,
                     artwork_url, source, soundcloud_synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'soundcloud', CURRENT_TIMESTAMP)""",
                (
                    soundcloud_id,
                    metadata.get("permalink_url") or "",
                    metadata.get("title") or "",
                    metadata.get("artist_name") or "Unknown",
                    (metadata.get("duration_ms") or 0) / 1000.0,
                    metadata.get("genre"),
                    metadata.get("artwork_url"),
                ),
            )
            track_id = cursor.lastrowid
        conn.execute(
            "UPDATE discovery_tracks SET local_track_id = ? WHERE soundcloud_id = ?",
            (track_id, soundcloud_id),
        )
        conn.execute(
            "UPDATE sc_artist_uploads SET local_track_id = ? WHERE soundcloud_id = ?",
            (track_id, soundcloud_id),
        )
        conn.commit()
    return int(track_id)


def get_current_decision(soundcloud_id: str) -> Optional[dict[str, Any]]:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sc_track_decisions WHERE soundcloud_id = ? AND is_current = 1",
            (soundcloud_id,),
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    if result.get("feature_snapshot"):
        result["feature_snapshot"] = json.loads(result["feature_snapshot"])
    return result


def get_decision_history(soundcloud_id: str) -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM sc_track_decisions WHERE soundcloud_id = ? ORDER BY decided_at, id",
            (soundcloud_id,),
        ).fetchall()
    result = [dict(row) for row in rows]
    for item in result:
        if item.get("feature_snapshot"):
            item["feature_snapshot"] = json.loads(item["feature_snapshot"])
    return result


def record_decision(
    soundcloud_id: str,
    decision: Decision,
    surface: str,
    model_version: Optional[str] = None,
    feature_snapshot: Optional[dict[str, Any]] = None,
    decided_at: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Append a decision and atomically make it the track's sole current row."""
    _validate_decision(decision)
    decided_at = decided_at or datetime.now(timezone.utc).isoformat()
    snapshot_json = (
        json.dumps(feature_snapshot, sort_keys=True, separators=(",", ":"))
        if feature_snapshot is not None
        else None
    )
    with get_db_connection() as conn:
        exists = conn.execute(
            """SELECT 1 FROM sc_artist_uploads WHERE soundcloud_id = ?
            UNION ALL SELECT 1 FROM discovery_tracks WHERE soundcloud_id = ? LIMIT 1""",
            (soundcloud_id, soundcloud_id),
        ).fetchone()
        if not exists:
            return None
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE sc_track_decisions SET is_current = 0 WHERE soundcloud_id = ? AND is_current = 1",
            (soundcloud_id,),
        )
        cursor = conn.execute(
            """INSERT INTO sc_track_decisions
                (soundcloud_id, decision, decided_at, surface, model_version,
                 feature_snapshot, is_current)
            VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (
                soundcloud_id,
                decision,
                decided_at,
                surface,
                model_version,
                snapshot_json,
            ),
        )
        legacy_status = _decision_to_legacy_status(decision)
        conn.execute(
            "UPDATE sc_artist_uploads SET status = ?, rated_at = ? WHERE soundcloud_id = ?",
            (legacy_status, decided_at, soundcloud_id),
        )
        conn.execute(
            """UPDATE discovery_tracks
            SET workflow_state = 'processed', status = ? WHERE soundcloud_id = ?""",
            (
                legacy_status if legacy_status != "hidden" else "dismissed",
                soundcloud_id,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM sc_track_decisions WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    result = dict(row)
    if snapshot_json is not None:
        result["feature_snapshot"] = feature_snapshot
    return result


def record_decisions(
    soundcloud_ids: list[str], decision: Decision, surface: str
) -> int:
    """Batch-append the same decision for builder finalization."""
    _validate_decision(decision)
    unique_ids = list(dict.fromkeys(soundcloud_ids))
    if not unique_ids:
        return 0
    decided_at = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        for start in range(0, len(unique_ids), 900):
            batch = unique_ids[start : start + 900]
            placeholders = ",".join("?" for _ in batch)
            conn.execute(
                f"UPDATE sc_track_decisions SET is_current = 0 "
                f"WHERE is_current = 1 AND soundcloud_id IN ({placeholders})",
                batch,
            )
        conn.executemany(
            """INSERT INTO sc_track_decisions
                (soundcloud_id, decision, decided_at, surface, is_current)
            VALUES (?, ?, ?, ?, 1)""",
            [(sc_id, decision, decided_at, surface) for sc_id in unique_ids],
        )
        legacy_status = _decision_to_legacy_status(decision)
        for start in range(0, len(unique_ids), 900):
            batch = unique_ids[start : start + 900]
            placeholders = ",".join("?" for _ in batch)
            conn.execute(
                f"UPDATE sc_artist_uploads SET status = ?, rated_at = ? "
                f"WHERE soundcloud_id IN ({placeholders})",
                [legacy_status, decided_at, *batch],
            )
            conn.execute(
                f"UPDATE discovery_tracks SET workflow_state = 'processed', status = ? "
                f"WHERE soundcloud_id IN ({placeholders})",
                [legacy_status if legacy_status != "hidden" else "dismissed", *batch],
            )
        conn.commit()
    return len(unique_ids)


def enqueue_keep_actions(soundcloud_id: str, playlist_name: str) -> None:
    """Persist the two idempotent external actions for a keep decision."""
    with get_db_connection() as conn:
        conn.executemany(
            """INSERT OR IGNORE INTO sc_feed_action_jobs
                (soundcloud_id, action_type, target_key) VALUES (?, ?, ?)""",
            (
                (soundcloud_id, "like", ""),
                (soundcloud_id, "monthly_playlist", playlist_name),
            ),
        )
        conn.commit()


def cancel_pending_actions(soundcloud_id: str) -> int:
    """Drop not-yet-done SC jobs when the current decision is no longer keep."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """DELETE FROM sc_feed_action_jobs
            WHERE soundcloud_id = ? AND status IN ('pending', 'error')""",
            (soundcloud_id,),
        )
        conn.commit()
        return cursor.rowcount


def claim_due_action() -> Optional[dict[str, Any]]:
    """Atomically claim the oldest due job for the single SC writer."""
    with get_db_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """SELECT * FROM sc_feed_action_jobs
            WHERE status IN ('pending', 'error') AND attempt_count < max_attempts
              AND next_attempt_at <= CURRENT_TIMESTAMP
            ORDER BY next_attempt_at, id LIMIT 1"""
        ).fetchone()
        if not row:
            conn.commit()
            return None
        conn.execute(
            """UPDATE sc_feed_action_jobs
            SET status = 'running', attempt_count = attempt_count + 1,
                updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (row["id"],),
        )
        conn.commit()
        claimed = dict(row)
        claimed["attempt_count"] += 1
        claimed["status"] = "running"
        return claimed


def get_next_action_delay() -> Optional[float]:
    """Seconds until the next retryable job becomes due."""
    with get_db_connection() as conn:
        row = conn.execute(
            """SELECT MIN(MAX(0, (julianday(next_attempt_at) - julianday('now'))
                                      * 86400.0)) AS delay
            FROM sc_feed_action_jobs
            WHERE status IN ('pending', 'error') AND attempt_count < max_attempts"""
        ).fetchone()
    return float(row["delay"]) if row and row["delay"] is not None else None


def complete_action(job_id: int) -> None:
    with get_db_connection() as conn:
        conn.execute(
            """UPDATE sc_feed_action_jobs SET status = 'complete', last_error = NULL,
                completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?""",
            (job_id,),
        )
        conn.commit()


def fail_action(job_id: int, error: str, attempt_count: int, max_attempts: int) -> None:
    """Persist bounded exponential backoff; terminal failures remain visible."""
    delay_seconds = min(3600, 2 ** max(0, attempt_count - 1) * 30)
    terminal = attempt_count >= max_attempts
    with get_db_connection() as conn:
        conn.execute(
            """UPDATE sc_feed_action_jobs SET status = 'error', last_error = ?,
                updated_at = CURRENT_TIMESTAMP,
                next_attempt_at = CASE WHEN ? THEN next_attempt_at
                    ELSE datetime('now', '+' || ? || ' seconds') END
            WHERE id = ?""",
            (error[:2000], int(terminal), delay_seconds, job_id),
        )
        conn.commit()


def recover_interrupted_actions() -> int:
    """Put jobs left running by a process death back into the durable queue."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """UPDATE sc_feed_action_jobs SET status = 'pending',
                next_attempt_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            WHERE status = 'running'"""
        )
        conn.commit()
        return cursor.rowcount


def reconcile_actions(soundcloud_id: Optional[str] = None) -> int:
    """Manual reconciliation: make unfinished jobs immediately retryable."""
    with get_db_connection() as conn:
        if soundcloud_id is None:
            cursor = conn.execute(
                """UPDATE sc_feed_action_jobs SET status = 'pending', attempt_count = 0,
                    next_attempt_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE status != 'complete'"""
            )
        else:
            cursor = conn.execute(
                """UPDATE sc_feed_action_jobs SET status = 'pending', attempt_count = 0,
                    next_attempt_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE soundcloud_id = ? AND status != 'complete'""",
                (soundcloud_id,),
            )
        conn.commit()
        return cursor.rowcount


def get_action_counts() -> dict[str, int]:
    """Job counts by status for the sync-status endpoint."""
    counts = {"pending": 0, "running": 0, "complete": 0, "error": 0}
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM sc_feed_action_jobs GROUP BY status"
        ).fetchall()
    for row in rows:
        counts[row["status"]] = row["n"]
    return counts


def get_contributing_artist_ids(soundcloud_id: str) -> list[int]:
    """Uploader plus every reposter of a track: the artists a decision trains."""
    with get_db_connection() as conn:
        rows = conn.execute(
            """SELECT discovery_artist_id FROM sc_artist_uploads WHERE soundcloud_id = ?
            UNION
            SELECT dtr.discovery_artist_id
            FROM discovery_track_reposters dtr
            JOIN discovery_tracks dt ON dt.id = dtr.discovery_track_id
            WHERE dt.soundcloud_id = ?""",
            (soundcloud_id, soundcloud_id),
        ).fetchall()
    return [row["discovery_artist_id"] for row in rows]


def get_action_state(soundcloud_id: str) -> dict[str, Optional[str]]:
    item: dict[str, Any] = {"soundcloud_id": soundcloud_id, "action_state": {}}
    with get_db_connection() as conn:
        _attach_action_states(conn, [item])
    return item["action_state"]


def get_upload(upload_id: int) -> Optional[dict[str, Any]]:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sc_artist_uploads WHERE id = ?", (upload_id,)
        ).fetchone()
    return dict(row) if row else None


def get_cached_monthly_playlist_id(name: str) -> Optional[str]:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT sc_playlist_id FROM sc_monthly_playlists WHERE name = ?", (name,)
        ).fetchone()
        if row:
            return row["sc_playlist_id"]
        row = conn.execute(
            """SELECT soundcloud_playlist_id FROM playlists
            WHERE name = ? AND soundcloud_playlist_id IS NOT NULL""",
            (name,),
        ).fetchone()
    return row["soundcloud_playlist_id"] if row else None


def cache_monthly_playlist_id(name: str, sc_playlist_id: str) -> None:
    with get_db_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sc_monthly_playlists (name, sc_playlist_id) VALUES (?, ?)",
            (name, sc_playlist_id),
        )
        conn.commit()
    logger.info(f"feed: cached monthly SC playlist '{name}' -> {sc_playlist_id}")
