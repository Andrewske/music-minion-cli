"""Not-for-feed flags and the filter rules that write them (#30).

Flags are not taste labels: they live in ``sc_track_flags``, never in
``sc_track_decisions``. An active (unrescued) flag hides a track from the
feed and keeps it out of artist stats and keep-model training. Rules never
delete track data; they only write flags, and a rescue only stamps
``rescued_at``. A rescued row is the track's permanent exemption from every
rule, so it outlives the rule that wrote it (``rule_id`` goes NULL).
"""

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from loguru import logger

from music_minion.core.database import get_db_connection
from web.backend.feed_filter_rules import (
    FLAG_REASONS,
    FLAG_SOURCES,
    first_matching_rule,
    rule_precision,
    validate_rule,
)
from web.backend.queries.feed import (
    get_contributing_artist_ids_for,
    set_track_note,
    utc_iso,
    window_params,
)

_RULE_FIELDS = ("name", "kind", "pattern", "threshold", "reason", "enabled")

_RULES_SQL = """
    SELECT r.id, r.name, r.kind, r.pattern, r.threshold, r.reason, r.enabled,
           r.seed_key, r.created_at, r.updated_at,
           COUNT(f.id) AS hits,
           COUNT(f.rescued_at) AS rescues
    FROM feed_filter_rules r
    LEFT JOIN sc_track_flags f ON f.rule_id = r.id AND f.source = 'rule'
    WHERE :rule_id IS NULL OR r.id = :rule_id
    GROUP BY r.id
    ORDER BY r.id
"""


def _row_to_rule(row: Any) -> dict[str, Any]:
    rule = dict(row)
    rule["enabled"] = bool(rule["enabled"])
    rule["precision"] = rule_precision(rule["hits"], rule["rescues"])
    return rule


def list_rules(rule_id: int | None = None) -> list[dict[str, Any]]:
    """Every rule with hit count, rescue count and precision."""
    with get_db_connection() as conn:
        rows = conn.execute(_RULES_SQL, {"rule_id": rule_id}).fetchall()
    return [_row_to_rule(row) for row in rows]


def get_rule(rule_id: int) -> dict[str, Any] | None:
    rules = list_rules(rule_id)
    return rules[0] if rules else None


def create_rule(fields: dict[str, Any]) -> dict[str, Any]:
    """Validate and insert a rule; ValueError carries the validation message."""
    rule = validate_rule(fields)
    with get_db_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO feed_filter_rules
                (name, kind, pattern, threshold, reason, enabled)
            VALUES (:name, :kind, :pattern, :threshold, :reason, :enabled)""",
            {**rule, "enabled": int(rule["enabled"])},
        )
        conn.commit()
        rule_id = int(cursor.lastrowid)
    logger.info(f"feed filters: created rule {rule_id} ({rule['kind']})")
    return get_rule(rule_id) or {}


def update_rule(rule_id: int, changes: dict[str, Any]) -> dict[str, Any] | None:
    """Apply a partial edit, re-validating the merged rule. None if missing.

    Existing flags stay put: an edit changes what the rule catches next.
    """
    current = get_rule(rule_id)
    if current is None:
        return None
    merged = {field: current[field] for field in _RULE_FIELDS}
    merged.update({k: v for k, v in changes.items() if k in _RULE_FIELDS})
    rule = validate_rule(merged)
    with get_db_connection() as conn:
        conn.execute(
            """UPDATE feed_filter_rules
            SET name = :name, kind = :kind, pattern = :pattern,
                threshold = :threshold, reason = :reason, enabled = :enabled,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = :id""",
            {**rule, "enabled": int(rule["enabled"]), "id": rule_id},
        )
        conn.commit()
    return get_rule(rule_id)


def delete_rule(rule_id: int) -> list[str] | None:
    """Delete a rule and its active flags; None when the rule doesn't exist.

    Returns the soundcloud ids released back to the feed. Rescued flags are
    kept: the v68 foreign key sets their ``rule_id`` to NULL, and the row
    still stops every other rule from flagging that track again.
    """
    with get_db_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        released = [
            row["soundcloud_id"]
            for row in conn.execute(
                """DELETE FROM sc_track_flags
                WHERE rule_id = ? AND source = 'rule' AND rescued_at IS NULL
                RETURNING soundcloud_id""",
                (rule_id,),
            ).fetchall()
        ]
        cursor = conn.execute("DELETE FROM feed_filter_rules WHERE id = ?", (rule_id,))
        if cursor.rowcount == 0:
            conn.rollback()
            return None
        conn.commit()
    return released


def _enabled_rules(conn: Any) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM feed_filter_rules WHERE enabled = 1 ORDER BY id"
    ).fetchall()
    return [dict(row) for row in rows]


# Unreviewed tracks no rule may touch yet: no current decision, never flagged
# and never rescued (a rescue is the user saying "this is a real track").
# Without explicit ids only the feed's window is scanned: the stale import
# holds ~226k tracks the feed never shows, and flagging them would bury the
# Settings list and skew precision.
_CANDIDATES_SQL = f"""
    WITH ids AS (
        SELECT dt.soundcloud_id FROM discovery_tracks dt
        WHERE dt.soundcloud_id IN (SELECT value FROM json_each(:ids))
           OR (:ids IS NULL AND (:since_seen IS NULL OR dt.first_seen >= :since_seen
               OR EXISTS (SELECT 1 FROM discovery_track_reposters dtr
                          WHERE dtr.discovery_track_id = dt.id
                            AND dtr.seen_at >= :since_seen)))
        UNION
        SELECT u.soundcloud_id FROM sc_artist_uploads u
        WHERE u.soundcloud_id IN (SELECT value FROM json_each(:ids))
           OR (:ids IS NULL AND (:since_event IS NULL
               OR {utc_iso("u.uploaded_at")} >= :since_event))
    )
    SELECT ids.soundcloud_id,
           COALESCE(u.title, dt.title) AS title,
           COALESCE(NULLIF(u.duration_ms, 0), dt.duration_ms, 0) AS duration_ms,
           COALESCE(u.genre, dt.genre) AS genre
    FROM ids
    LEFT JOIN sc_artist_uploads u ON u.soundcloud_id = ids.soundcloud_id
    LEFT JOIN discovery_tracks dt ON dt.soundcloud_id = ids.soundcloud_id
    WHERE NOT EXISTS (
            SELECT 1 FROM sc_track_decisions d
            WHERE d.soundcloud_id = ids.soundcloud_id AND d.is_current = 1)
      AND NOT EXISTS (
            SELECT 1 FROM sc_track_flags f WHERE f.soundcloud_id = ids.soundcloud_id)
"""


def _rule_flags(
    tracks: list[dict[str, Any]], rules: list[dict[str, Any]]
) -> list[tuple[str, str, int]]:
    """(soundcloud_id, reason, rule_id) for each track the first rule catches."""
    flags = []
    for track in tracks:
        rule = first_matching_rule(track, rules)
        if rule is not None:
            flags.append((track["soundcloud_id"], rule["reason"], rule["id"]))
    return flags


# Matching runs in Python between the read and the write, so every insert
# re-checks, inside the write transaction, that the rule still exists
# unedited and enabled and that the track is still undecided with no flag
# (active or rescued). A rule deleted, disabled or edited mid-run, or a track
# rated or rescued mid-run, writes nothing.
_INSERT_RULE_FLAG_SQL = """
    INSERT OR IGNORE INTO sc_track_flags (soundcloud_id, reason, source, rule_id)
    SELECT :soundcloud_id, :reason, 'rule', :rule_id
    WHERE EXISTS (
            SELECT 1 FROM feed_filter_rules r
            WHERE r.id = :rule_id AND r.enabled = 1 AND r.updated_at = :updated_at)
      AND NOT EXISTS (
            SELECT 1 FROM sc_track_decisions d
            WHERE d.soundcloud_id = :soundcloud_id AND d.is_current = 1)
      AND NOT EXISTS (
            SELECT 1 FROM sc_track_flags f WHERE f.soundcloud_id = :soundcloud_id)
"""


def _write_rule_flags(
    conn: Any, flags: list[tuple[str, str, int]], rules: list[dict[str, Any]]
) -> int:
    """Insert flags under BEGIN IMMEDIATE, revalidating each; returns rows written."""
    updated_at = {rule["id"]: rule["updated_at"] for rule in rules}
    conn.execute("BEGIN IMMEDIATE")
    written = 0
    for soundcloud_id, reason, rule_id in flags:
        params = {
            "soundcloud_id": soundcloud_id,
            "reason": reason,
            "rule_id": rule_id,
            "updated_at": updated_at[rule_id],
        }
        written += conn.execute(_INSERT_RULE_FLAG_SQL, params).rowcount
    conn.commit()
    return written


def apply_rules(soundcloud_ids: list[str] | None = None) -> int:
    """Flag unreviewed tracks caught by an enabled rule; returns flags written.

    Pass the ids just ingested, or None to re-run over every unreviewed track
    inside the feed window. Rules only flag undecided tracks, which carry no
    artist-stat weight, so no stats refresh is needed here.
    """
    if soundcloud_ids is not None and not soundcloud_ids:
        return 0
    ids_json = None if soundcloud_ids is None else json.dumps(soundcloud_ids)
    with get_db_connection() as conn:
        rules = _enabled_rules(conn)
        if not rules:
            return 0
        params = {"ids": ids_json, **window_params()}
        tracks = [dict(row) for row in conn.execute(_CANDIDATES_SQL, params)]
        flags = _rule_flags(tracks, rules)
        written = _write_rule_flags(conn, flags, rules) if flags else 0
    if written:
        logger.info(f"feed filters: flagged {written} of {len(tracks)} tracks")
    return written


def filter_ingested(soundcloud_ids: list[str]) -> int:
    """Ingest hook: a filter failure must never fail the sync that called it."""
    try:
        return apply_rules(list(dict.fromkeys(soundcloud_ids)))
    except sqlite3.Error:
        logger.exception(f"feed filters: rules failed for {len(soundcloud_ids)} tracks")
        return 0


def refresh_artist_stats_for(soundcloud_ids: Iterable[str]) -> None:
    """Recompute persisted artist aggregates after flags change which tracks count.

    One batched recalc for every uploader/reposter of the given tracks. Runs
    as a background task, so failures are logged, never raised.
    """
    # Local import: queries.discovery imports this module for its ingest hook.
    from web.backend.queries import discovery as discovery_queries

    unique_ids = list(dict.fromkeys(soundcloud_ids))
    if not unique_ids:
        return
    try:
        artist_ids = get_contributing_artist_ids_for(unique_ids)
        if artist_ids:
            discovery_queries.recalculate_artist_stats(artist_ids)
    except sqlite3.Error:
        logger.exception(
            f"feed filters: artist stats refresh failed for {len(unique_ids)} tracks"
        )


def active_flagged_ids(soundcloud_ids: Iterable[str]) -> set[str]:
    """The subset of ids with an active (unrescued) not-for-feed flag."""
    ids_json = json.dumps(list(dict.fromkeys(soundcloud_ids)))
    with get_db_connection() as conn:
        rows = conn.execute(
            """SELECT soundcloud_id FROM sc_track_flags
            WHERE rescued_at IS NULL
              AND soundcloud_id IN (SELECT value FROM json_each(?))""",
            (ids_json,),
        ).fetchall()
    return {row["soundcloud_id"] for row in rows}


def _validate_reason(reason: str) -> None:
    if reason not in FLAG_REASONS:
        raise ValueError(f"Invalid reason {reason!r}; valid reasons are {FLAG_REASONS}")


def get_active_flag(soundcloud_id: str) -> dict[str, Any] | None:
    with get_db_connection() as conn:
        row = conn.execute(
            """SELECT * FROM sc_track_flags
            WHERE soundcloud_id = ? AND rescued_at IS NULL""",
            (soundcloud_id,),
        ).fetchone()
    return dict(row) if row else None


def flag_track(
    soundcloud_id: str, reason: str, note: str | None = None
) -> dict[str, Any]:
    """User flag: hides the track. An existing active flag is kept as-is.

    The optional note goes to the shared per-track notes table.
    """
    _validate_reason(reason)
    with get_db_connection() as conn:
        conn.execute(
            """INSERT INTO sc_track_flags (soundcloud_id, reason, source)
            SELECT ?, ?, 'user'
            WHERE NOT EXISTS (
                SELECT 1 FROM sc_track_flags
                WHERE soundcloud_id = ? AND rescued_at IS NULL)""",
            (soundcloud_id, reason, soundcloud_id),
        )
        conn.commit()
    if note is not None and note.strip():
        set_track_note(soundcloud_id, note)
    return get_active_flag(soundcloud_id) or {}


def unflag_track(soundcloud_id: str) -> dict[str, Any] | None:
    """Return a flagged track to the feed. None when nothing was flagged.

    A user flag is simply undone (deleted). A rule/agent flag is rescued:
    ``rescued_at`` is stamped so the rule's precision drops and no rule
    flags the track again.
    """
    flag = get_active_flag(soundcloud_id)
    if flag is None:
        return None
    rescued_at = datetime.now(UTC).isoformat()
    with get_db_connection() as conn:
        if flag["source"] == "user":
            conn.execute("DELETE FROM sc_track_flags WHERE id = ?", (flag["id"],))
        else:
            conn.execute(
                "UPDATE sc_track_flags SET rescued_at = ? WHERE id = ?",
                (rescued_at, flag["id"]),
            )
        conn.commit()
    if flag["source"] == "user":
        return {**flag, "removed": True}
    return {**flag, "rescued_at": rescued_at, "removed": False}


_FLAGGED_SQL = """
    SELECT f.id AS flag_id, f.soundcloud_id, f.reason, f.source, f.rule_id,
           f.created_at, r.name AS rule_name,
           COALESCE(u.local_track_id, dt.local_track_id) AS local_track_id,
           COALESCE(u.title, dt.title) AS title,
           COALESCE(da.display_name, uda.display_name, dt.artist_name) AS artist_name,
           COALESCE(u.artwork_url, dt.artwork_url) AS artwork_url,
           COALESCE(u.permalink_url, dt.permalink_url) AS permalink_url,
           COALESCE(NULLIF(u.duration_ms, 0), dt.duration_ms, 0) AS duration_ms,
           COALESCE(u.access, dt.access) AS access,
           n.note
    FROM sc_track_flags f
    LEFT JOIN feed_filter_rules r ON r.id = f.rule_id
    LEFT JOIN sc_artist_uploads u ON u.soundcloud_id = f.soundcloud_id
    LEFT JOIN discovery_artists da ON da.id = u.discovery_artist_id
    LEFT JOIN discovery_tracks dt ON dt.soundcloud_id = f.soundcloud_id
    LEFT JOIN discovery_artists uda
      ON uda.soundcloud_user_id = dt.uploader_soundcloud_id
    LEFT JOIN sc_track_notes n ON n.soundcloud_id = f.soundcloud_id
    WHERE f.rescued_at IS NULL
      AND f.source IN (SELECT value FROM json_each(:sources))
      AND (:rule_id IS NULL OR f.rule_id = :rule_id)
      AND (:cursor_id IS NULL OR f.id < :cursor_id)
    ORDER BY f.id DESC
    LIMIT :limit
"""


def list_flagged(
    sources: tuple[str, ...] = ("rule", "agent"),
    rule_id: int | None = None,
    limit: int = 50,
    cursor_id: int | None = None,
) -> list[dict[str, Any]]:
    """Active flags newest first with track metadata; cursor is the last flag_id."""
    invalid = [source for source in sources if source not in FLAG_SOURCES]
    if invalid or not sources:
        raise ValueError(f"Invalid flag sources {sources!r}; valid are {FLAG_SOURCES}")
    params = {
        "sources": json.dumps(list(sources)),
        "rule_id": rule_id,
        "limit": max(1, min(limit, 100)),
        "cursor_id": cursor_id,
    }
    with get_db_connection() as conn:
        rows = conn.execute(_FLAGGED_SQL, params).fetchall()
    return [dict(row) for row in rows]
