"""Reviewed-track loading for feed Insights and the Jev taste profile (#31).

Only current keep / not quite / nope verdicts count: legacy ``hide`` rows
were never a taste label and not-for-feed flagged tracks are "not a track",
so both stay out of every stat, exactly like artist stats.
"""

from typing import Any

from music_minion.core.database import get_db_connection
from web.backend import feed_insights
from web.backend.feed_filter_rules import not_flagged_sql
from web.backend.queries.feed import utc_iso
from web.backend.soundcloud_metadata import parse_soundcloud_datetime

_REPOSTER_SEPARATOR = "\x1f"
MAX_INSIGHT_TRACKS = 200

_REVIEWED_TRACKS_SQL = f"""
    SELECT d.id AS decision_id, d.soundcloud_id, d.decision, d.decided_at,
           {utc_iso("d.decided_at")} AS decided_key,
           COALESCE(u.local_track_id, dt.local_track_id) AS local_track_id,
           COALESCE(u.title, dt.title) AS title,
           COALESCE(u.genre, dt.genre) AS genre,
           COALESCE(u.tag_list, dt.tag_list) AS tag_list,
           COALESCE(da.display_name, uda.display_name, dt.artist_name) AS uploader,
           COALESCE(u.artwork_url, dt.artwork_url) AS artwork_url,
           COALESCE(u.permalink_url, dt.permalink_url) AS permalink_url,
           COALESCE(NULLIF(u.duration_ms, 0), dt.duration_ms, 0) AS duration_ms,
           COALESCE(u.access, dt.access) AS access,
           COALESCE(u.released_at, dt.released_at, u.uploaded_at, dt.uploaded_at)
               AS released_at,
           n.note,
           (SELECT GROUP_CONCAT(ra.display_name, char(31))
            FROM discovery_track_reposters dtr
            JOIN discovery_artists ra ON ra.id = dtr.discovery_artist_id
            WHERE dtr.discovery_track_id = dt.id) AS reposter_names
    FROM sc_track_decisions d
    LEFT JOIN sc_artist_uploads u ON u.soundcloud_id = d.soundcloud_id
    LEFT JOIN discovery_artists da ON da.id = u.discovery_artist_id
    LEFT JOIN discovery_tracks dt ON dt.soundcloud_id = d.soundcloud_id
    LEFT JOIN discovery_artists uda
      ON uda.soundcloud_user_id = dt.uploader_soundcloud_id
    LEFT JOIN sc_track_notes n ON n.soundcloud_id = d.soundcloud_id
    WHERE d.is_current = 1 AND d.decision IN ('keep', 'not_quite', 'nope')
      AND {not_flagged_sql("d.soundcloud_id")}
    ORDER BY {utc_iso("d.decided_at")} DESC, d.id DESC
"""


def _age_days(released_at: Any, decided_at: Any) -> float | None:
    released = parse_soundcloud_datetime(released_at)
    decided = parse_soundcloud_datetime(decided_at)
    if released is None or decided is None:
        return None
    return round((decided - released).total_seconds() / 86_400, 1)


def _row_to_track(row: Any) -> dict[str, Any]:
    track = dict(row)
    names = track.pop("reposter_names") or ""
    track["reposters"] = sorted(set(filter(None, names.split(_REPOSTER_SEPARATOR))))
    track["age_days"] = _age_days(track["released_at"], track["decided_at"])
    return track


def load_reviewed_tracks() -> list[dict[str, Any]]:
    """Every current, unflagged keep / not quite / nope, newest verdict first."""
    with get_db_connection() as conn:
        rows = conn.execute(_REVIEWED_TRACKS_SQL).fetchall()
    return [_row_to_track(row) for row in rows]


def get_insights(dimension: str, min_count: int) -> dict[str, Any]:
    """Feature table for one dimension plus the overall baseline."""
    feed_insights.validate_dimension(dimension)
    tracks = load_reviewed_tracks()
    return {
        "dimension": dimension,
        "min_count": min_count,
        "overall": {
            "seen": len(tracks),
            "keep_pct": feed_insights.overall_keep_pct(tracks),
        },
        "rows": feed_insights.aggregate(tracks, dimension, min_count),
    }


def get_insight_tracks(dimension: str, value: str) -> dict[str, Any]:
    """Reviewed tracks behind one Insights row, newest verdict first."""
    feed_insights.validate_dimension(dimension)
    matches = feed_insights.matching_tracks(load_reviewed_tracks(), dimension, value)
    return {
        "dimension": dimension,
        "value": value,
        "total": len(matches),
        "items": matches[:MAX_INSIGHT_TRACKS],
    }


def _recent_notes(conn: Any, limit: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"""SELECT n.note, d.decision,
               COALESCE(u.title, dt.title) AS title
        FROM sc_track_notes n
        JOIN sc_track_decisions d
          ON d.soundcloud_id = n.soundcloud_id AND d.is_current = 1
        LEFT JOIN sc_artist_uploads u ON u.soundcloud_id = n.soundcloud_id
        LEFT JOIN discovery_tracks dt ON dt.soundcloud_id = n.soundcloud_id
        WHERE d.decision IN ('not_quite', 'nope')
          AND {not_flagged_sql("n.soundcloud_id")}
        ORDER BY {utc_iso("n.updated_at")} DESC, n.rowid DESC
        LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def load_recent_notes(limit: int = 10) -> list[dict[str, Any]]:
    """Latest notes Kevin left on not-quite / nope verdicts."""
    with get_db_connection() as conn:
        return _recent_notes(conn, limit)


def taste_evidence() -> str:
    """Generated taste-profile section: top lift features plus recent notes."""
    tracks = load_reviewed_tracks()
    return feed_insights.format_taste_evidence(
        feed_insights.overall_keep_pct(tracks),
        *feed_insights.top_lift_features(tracks, feed_insights.PROFILE_DIMENSIONS),
        load_recent_notes(),
    )
