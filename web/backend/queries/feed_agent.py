"""Persistence for the feed agent (#31): Jev mix classifications and mined
rule suggestions.

The agent only ever writes flags (``source='agent'``) or suggestions. Rules
are created by Kevin accepting a suggestion, through the normal validated
rule-creation path, and verdicts are never touched here.
"""

import json
import uuid
from typing import Any

from loguru import logger

from music_minion.core.database import get_db_connection
from web.backend import rule_suggestions
from web.backend.feed_filter_rules import flaggable_track_sql
from web.backend.queries import feed_filters as filter_queries
from web.backend.queries import insights as insight_queries
from web.backend.soundcloud_metadata import parse_tag_list

CLASSIFICATION_STATUSES: tuple[str, ...] = (
    "auto_flagged",
    "pending",
    "below_threshold",
    "confirmed",
    "dismissed",
)

_TRACK_COLUMNS = """
    COALESCE(u.title, dt.title) AS title,
    COALESCE(u.genre, dt.genre) AS genre,
    COALESCE(u.tag_list, dt.tag_list) AS tag_list,
    COALESCE(NULLIF(u.duration_ms, 0), dt.duration_ms, 0) AS duration_ms,
    COALESCE(da.display_name, uda.display_name, dt.artist_name) AS uploader
"""

_TRACK_JOINS = (
    """
    LEFT JOIN sc_artist_uploads u ON u.soundcloud_id = {column}
    LEFT JOIN discovery_artists da ON da.id = u.discovery_artist_id
    LEFT JOIN discovery_tracks dt ON dt.soundcloud_id = {column}
"""
    + insight_queries.UPLOADER_ARTIST_JOIN
)


def _track_dict(row: Any) -> dict[str, Any]:
    track = dict(row)
    track["tags"] = parse_tag_list(track.pop("tag_list", None))
    return track


# ---------------------------------------------------------------------------
# Few-shot examples and flag history
# ---------------------------------------------------------------------------

# Positives: Kevin's own flags (including suggestions he confirmed).
_USER_FLAGS_SQL = f"""
    SELECT f.soundcloud_id, f.reason, {_TRACK_COLUMNS}
    FROM sc_track_flags f
    {_TRACK_JOINS.format(column="f.soundcloud_id")}
    WHERE f.source = 'user' AND f.rescued_at IS NULL
    GROUP BY f.id
    ORDER BY f.id DESC
    LIMIT :limit
"""

# Negatives: rule/agent flags Kevin rescued, and suggestions he dismissed.
_NOT_MIX_SQL = f"""
    SELECT x.soundcloud_id, {_TRACK_COLUMNS}
    FROM (
        SELECT soundcloud_id, rescued_at AS at FROM sc_track_flags
        WHERE rescued_at IS NOT NULL
        UNION
        SELECT soundcloud_id, updated_at AS at FROM sc_track_classifications
        WHERE status = 'dismissed'
    ) x
    {_TRACK_JOINS.format(column="x.soundcloud_id")}
    GROUP BY x.soundcloud_id
    ORDER BY MAX(x.at) DESC
    LIMIT :limit
"""


def load_user_flags(limit: int = 500) -> list[dict[str, Any]]:
    """Kevin's active flags, newest first, with title/genre/tags/duration."""
    with get_db_connection() as conn:
        rows = conn.execute(_USER_FLAGS_SQL, {"limit": limit}).fetchall()
    return [_track_dict(row) for row in rows]


def load_not_mix_examples(limit: int = 500) -> list[dict[str, Any]]:
    """Tracks Kevin said are real tracks: rescues and dismissed suggestions."""
    with get_db_connection() as conn:
        rows = conn.execute(_NOT_MIX_SQL, {"limit": limit}).fetchall()
    return [_track_dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Classifications
# ---------------------------------------------------------------------------


def classified_ids(conn: Any) -> set[str]:
    rows = conn.execute("SELECT soundcloud_id FROM sc_track_classifications")
    return {row["soundcloud_id"] for row in rows}


def ambiguous_pool(conn: Any) -> list[dict[str, Any]]:
    """Unreviewed, never-flagged, unclassified tracks in the feed window,
    one entry per track (uploader aliases can repeat a candidate row)."""
    done = classified_ids(conn)
    pool: dict[str, dict[str, Any]] = {}
    for track in filter_queries.unreviewed_candidates(conn, None):
        if track["soundcloud_id"] not in done:
            pool.setdefault(track["soundcloud_id"], track)
    return list(pool.values())


# A run claims its tracks before asking Jev, so overlapping runs never ask
# about (or flag) the same track twice. Claims left by a crashed run expire.
STALE_CLAIM_MINUTES = 60


def new_claim_token() -> str:
    return f"claim:{uuid.uuid4().hex}"


def expire_stale_claims(conn: Any) -> None:
    conn.execute(
        """DELETE FROM sc_track_classifications WHERE status = 'claimed'
          AND created_at < datetime('now', ?)""",
        (f"-{STALE_CLAIM_MINUTES} minutes",),
    )
    conn.commit()


def claim_tracks(
    conn: Any, tracks: list[dict[str, Any]], model_id: str, token: str
) -> list[dict[str, Any]]:
    """Reserve unclassified tracks for this run; returns the ones it won."""
    claimed = [
        track
        for track in tracks
        if conn.execute(
            """INSERT OR IGNORE INTO sc_track_classifications
                (soundcloud_id, model_id, status, state_sent)
            VALUES (?, ?, 'claimed', ?)""",
            (track["soundcloud_id"], model_id, token),
        ).rowcount
        == 1
    ]
    conn.commit()
    return claimed


def release_claims(conn: Any, token: str) -> None:
    """Drop this run's unanswered claims so a later run can ask again."""
    conn.execute(
        """DELETE FROM sc_track_classifications
        WHERE status = 'claimed' AND state_sent = ?""",
        (token,),
    )
    conn.commit()


_SAVE_CLASSIFICATION_SQL = """
    UPDATE sc_track_classifications
    SET model_id = :model_id, mix_probability = :mix_probability,
        podcast_probability = :podcast_probability, status = :status,
        state_sent = :state, updated_at = CURRENT_TIMESTAMP
    WHERE soundcloud_id = :soundcloud_id AND status = 'claimed'
      AND state_sent = :token
"""

# The pool was read before the Jev call, so recheck at write time (as rule
# flags do): a track rated, flagged or rescued meanwhile is left alone.
_INSERT_AGENT_FLAG_SQL = f"""
    INSERT OR IGNORE INTO sc_track_flags (soundcloud_id, reason, source, confidence)
    SELECT :soundcloud_id, :reason, 'agent', :mix_probability
    WHERE {flaggable_track_sql(":soundcloud_id")}
"""


def save_classification(
    conn: Any, result: dict[str, Any], model_id: str, state: str, token: str
) -> bool:
    """Fill in this run's claim; an auto_flagged result also writes the flag.

    False (and no flag) when the claim is gone, so a replayed or expired
    result can never flag a track another run or Kevin already handled.
    """
    params = {**result, "model_id": model_id, "state": state, "token": token}
    if conn.execute(_SAVE_CLASSIFICATION_SQL, params).rowcount != 1:
        return False
    if result["status"] == "auto_flagged":
        conn.execute(_INSERT_AGENT_FLAG_SQL, result)
    return True


_CLASSIFICATIONS_SQL = f"""
    SELECT c.id, c.soundcloud_id, c.model_id, c.mix_probability,
           c.podcast_probability, c.status, c.created_at,
           COALESCE(u.local_track_id, dt.local_track_id) AS local_track_id,
           COALESCE(u.artwork_url, dt.artwork_url) AS artwork_url,
           COALESCE(u.permalink_url, dt.permalink_url) AS permalink_url,
           COALESCE(u.access, dt.access) AS access,
           {_TRACK_COLUMNS}
    FROM sc_track_classifications c
    {_TRACK_JOINS.format(column="c.soundcloud_id")}
    WHERE c.status = :status
    GROUP BY c.id
    ORDER BY c.mix_probability DESC, c.id DESC
    LIMIT :limit
"""


def list_classifications(status: str, limit: int = 100) -> list[dict[str, Any]]:
    """Classifications in one status, most likely mixes first."""
    if status not in CLASSIFICATION_STATUSES:
        raise ValueError(
            f"Invalid classification status {status!r}; "
            f"valid are {CLASSIFICATION_STATUSES}"
        )
    params = {"status": status, "limit": max(1, min(limit, 200))}
    with get_db_connection() as conn:
        rows = conn.execute(_CLASSIFICATIONS_SQL, params).fetchall()
    return [_track_dict(row) for row in rows]


def get_classification(classification_id: int) -> dict[str, Any] | None:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM sc_track_classifications WHERE id = ?",
            (classification_id,),
        ).fetchone()
    return dict(row) if row else None


def _set_classification_status(classification_id: int, status: str) -> None:
    with get_db_connection() as conn:
        conn.execute(
            """UPDATE sc_track_classifications
            SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (status, classification_id),
        )
        conn.commit()


def resolve_classification(
    classification_id: int, confirm: bool
) -> dict[str, Any] | None:
    """Confirm a pending suggestion (Kevin's own flag) or dismiss it.

    None when missing; ValueError when it is no longer pending.
    """
    current = get_classification(classification_id)
    if current is None:
        return None
    if current["status"] != "pending":
        raise ValueError(
            f"Classification {classification_id} is {current['status']}, not pending"
        )
    if confirm:
        reason = (
            "podcast" if (current["podcast_probability"] or 0) > 0.5 else "live_mix"
        )
        filter_queries.flag_track(current["soundcloud_id"], reason)
    _set_classification_status(
        classification_id, "confirmed" if confirm else "dismissed"
    )
    return get_classification(classification_id)


# ---------------------------------------------------------------------------
# Rule suggestions
# ---------------------------------------------------------------------------

_UPSERT_SUGGESTION_SQL = """
    INSERT INTO feed_rule_suggestions
        (signature, name, kind, pattern, threshold, reason, support, counter,
         evidence)
    VALUES (:signature, :name, :kind, :pattern, :threshold, :reason, :support,
            :counter, :evidence)
    ON CONFLICT(signature) DO UPDATE SET
        name = excluded.name, reason = excluded.reason,
        support = excluded.support, counter = excluded.counter,
        evidence = excluded.evidence, updated_at = CURRENT_TIMESTAMP
    WHERE feed_rule_suggestions.status = 'pending'
"""


def save_suggestions(suggestions: list[dict[str, Any]]) -> int:
    """Upsert mined suggestions; pending ones that no longer qualify are dropped.

    Accepted and dismissed suggestions keep their status, so a dismissed
    suggestion never comes back.
    """
    signatures = json.dumps([item["signature"] for item in suggestions])
    with get_db_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """DELETE FROM feed_rule_suggestions WHERE status = 'pending'
              AND signature NOT IN (SELECT value FROM json_each(?))""",
            (signatures,),
        )
        conn.executemany(_UPSERT_SUGGESTION_SQL, suggestions)
        conn.commit()
        row = conn.execute(
            "SELECT COUNT(*) FROM feed_rule_suggestions WHERE status = 'pending'"
        ).fetchone()
    return int(row[0])


def resolved_signatures() -> set[str]:
    """Signatures Kevin already accepted or dismissed: never suggested again."""
    with get_db_connection() as conn:
        rows = conn.execute(
            "SELECT signature FROM feed_rule_suggestions WHERE status != 'pending'"
        ).fetchall()
    return {row["signature"] for row in rows}


def mine_rule_suggestions() -> dict[str, Any]:
    """Re-mine Kevin's flags and rescues; returns the pending suggestions."""
    mined = rule_suggestions.mine_suggestions(
        load_user_flags(),
        load_not_mix_examples(),
        insight_queries.load_reviewed_tracks(),
        filter_queries.list_rules(),
        resolved_signatures(),
    )
    save_suggestions(mined)
    logger.info(f"feed agent: mined {len(mined)} rule suggestions")
    return {"mined": len(mined), "suggestions": list_suggestions("pending")}


def list_suggestions(status: str = "pending") -> list[dict[str, Any]]:
    with get_db_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM feed_rule_suggestions WHERE status = ?
            ORDER BY support DESC, counter ASC, id""",
            (status,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_suggestion(suggestion_id: int) -> dict[str, Any] | None:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM feed_rule_suggestions WHERE id = ?", (suggestion_id,)
        ).fetchone()
    return dict(row) if row else None


def _pending_suggestion(suggestion_id: int) -> dict[str, Any] | None:
    suggestion = get_suggestion(suggestion_id)
    if suggestion is not None and suggestion["status"] != "pending":
        raise ValueError(
            f"Suggestion {suggestion_id} is {suggestion['status']}, not pending"
        )
    return suggestion


def accept_suggestion(
    suggestion_id: int, overrides: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """Create a real rule from a suggestion via the validated rule path.

    `overrides` lets Kevin tweak name/pattern/threshold/reason first. None
    when missing; ValueError when not pending or the rule is invalid.
    """
    suggestion = _pending_suggestion(suggestion_id)
    if suggestion is None:
        return None
    fields = {key: suggestion[key] for key in ("name", "kind", "pattern", "threshold")}
    fields["reason"] = suggestion["reason"]
    fields.update({k: v for k, v in (overrides or {}).items() if v is not None})
    rule = filter_queries.create_rule(fields)
    with get_db_connection() as conn:
        conn.execute(
            """UPDATE feed_rule_suggestions SET status = 'accepted', rule_id = ?,
                updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (rule["id"], suggestion_id),
        )
        conn.commit()
    logger.info(f"feed agent: suggestion {suggestion_id} accepted as rule {rule['id']}")
    return {"suggestion": get_suggestion(suggestion_id), "rule": rule}


def dismiss_suggestion(suggestion_id: int) -> dict[str, Any] | None:
    if _pending_suggestion(suggestion_id) is None:
        return None
    with get_db_connection() as conn:
        conn.execute(
            """UPDATE feed_rule_suggestions SET status = 'dismissed',
                updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (suggestion_id,),
        )
        conn.commit()
    return get_suggestion(suggestion_id)
