"""Stories page: followed artists' recent reposts + uploads, one artist at a time.

One SQL pass returns a row per (artist, track) in the window with every field
the page needs, including the "listened" signals (LISTEN_SOURCES). Python only groups the
rows into artists, sorts, and drops artists with nothing left to hear.
"""

from datetime import UTC, datetime, timedelta
from itertools import groupby
from typing import Any

from music_minion.core.database import get_db_connection
from web.backend.feed_filter_rules import not_flagged_sql
from web.backend.queries.feed import DECISIONS, utc_iso
from web.backend.sc_likes import sc_liked_sql

MIN_DAYS = 1
MAX_DAYS = 30
LISTEN_SOURCES: tuple[str, ...] = (
    "explicit",
    "decision",
    "library",
    "played",
    "liked",
)

_ISO_Z = "%Y-%m-%dT%H:%M:%SZ"

# Exact repost times keep SC's raw '2026/11/09 07:08:08 +0000'; approximate
# ones are NULL and fall back to when sync saw them. seen_at alone can't
# prefilter: a re-repost bumps reposted_at but keeps the old seen_at.
_REPOST_AT = f"COALESCE({utc_iso('dtr.reposted_at')}, {utc_iso('dtr.seen_at')})"
# Cheap raw-string prefilter, each branch in that branch's stored format, so
# the 300k-row normalization only runs on candidates. Unknown formats skip
# the prefilter and get the exact normalized check.
_REPOST_PREFILTER = """(
    (COALESCE(dtr.reposted_at, '') = '' AND dtr.seen_at >= :since_seen)
    OR (dtr.reposted_at LIKE '____/__/__ %' AND dtr.reposted_at >= :since_raw)
    OR (dtr.reposted_at != '' AND dtr.reposted_at NOT LIKE '____/__/__ %')
)"""
_UPLOAD_AT = utc_iso("u.uploaded_at")
_PLAYABLE = "({alias}.access IS NULL OR {alias}.access = 'playable')"

_EVENTS_SQL = f"""
    WITH events AS (
        SELECT da.id AS artist_id, dt.soundcloud_id, 'repost' AS kind,
               {_REPOST_AT} AS activity_at, dt.title,
               COALESCE(uda.display_name, dt.artist_name) AS artist_name,
               dt.artwork_url, dt.permalink_url, dt.duration_ms, dt.local_track_id
        FROM discovery_artists da
        JOIN discovery_track_reposters dtr ON dtr.discovery_artist_id = da.id
        JOIN discovery_tracks dt ON dt.id = dtr.discovery_track_id
        LEFT JOIN discovery_artists uda
          ON uda.soundcloud_user_id = dt.uploader_soundcloud_id
        WHERE da.is_following = 1 AND {_PLAYABLE.format(alias="dt")}
          AND {_REPOST_PREFILTER} AND {_REPOST_AT} >= :since
        UNION ALL
        SELECT da.id, u.soundcloud_id, 'upload', {_UPLOAD_AT}, u.title,
               da.display_name, u.artwork_url, u.permalink_url, u.duration_ms,
               u.local_track_id
        FROM discovery_artists da
        JOIN sc_artist_uploads u ON u.discovery_artist_id = da.id
        WHERE da.is_following = 1 AND {_PLAYABLE.format(alias="u")}
          AND {_UPLOAD_AT} >= :since
    ),
    ranked AS (
        SELECT e.*,
               MAX(activity_at) OVER w AS latest_at,
               ROW_NUMBER() OVER (
                   PARTITION BY artist_id, soundcloud_id
                   ORDER BY kind = 'upload' DESC, activity_at DESC
               ) AS rn
        FROM events e
        WINDOW w AS (PARTITION BY artist_id, soundcloud_id)
    )
"""

# tracks is indexed on (source, soundcloud_id), so per-row lookups by
# soundcloud_id alone scan the table (~36s for 2.5k rows). Each signal is
# instead aggregated once over the window's distinct ids.
_STORIES_SQL = f"""
    {_EVENTS_SQL},
    window_ids AS MATERIALIZED (
        SELECT DISTINCT soundcloud_id FROM ranked WHERE rn = 1
    ),
    lib AS (
        SELECT t.soundcloud_id,
               MIN(CASE WHEN t.source = 'soundcloud' THEN t.id END) AS sc_track_id,
               MIN(t.id) AS any_track_id,
               MAX(COALESCE(t.local_path, '') != ''
                   OR EXISTS (SELECT 1 FROM playlist_tracks pt
                              WHERE pt.track_id = t.id)) AS in_library,
               -- position_ms holds listen duration, written when a play ends.
               MAX(EXISTS (SELECT 1 FROM radio_history rh
                           WHERE rh.track_id = t.id
                             AND rh.position_ms >= 5000)) AS played
        FROM tracks t
        WHERE t.soundcloud_id IN (SELECT soundcloud_id FROM window_ids)
        GROUP BY t.soundcloud_id
    ),
    pred AS (
        SELECT soundcloud_id, probability FROM (
            SELECT p.soundcloud_id, p.probability, ROW_NUMBER() OVER (
                PARTITION BY p.soundcloud_id ORDER BY p.created_at DESC, p.id DESC
            ) AS prn
            FROM sc_track_predictions p
            WHERE p.soundcloud_id IN (SELECT soundcloud_id FROM window_ids)
        ) WHERE prn = 1
    ),
    sc_like_job AS (
        SELECT soundcloud_id, status FROM sc_feed_action_jobs
        WHERE action_type = 'like'
          AND soundcloud_id IN (SELECT soundcloud_id FROM window_ids)
    )
    SELECT r.artist_id, da.display_name, da.slug, da.avatar_url,
           r.soundcloud_id, r.kind, r.latest_at AS activity_at, r.title,
           r.artist_name, r.artwork_url, r.permalink_url, r.duration_ms,
           COALESCE(r.local_track_id, lib.sc_track_id, lib.any_track_id)
               AS local_track_id,
           pred.probability AS score,
           d.decision,
           l.soundcloud_id IS NOT NULL AS listen_explicit,
           d.decision IS NOT NULL AS listen_decision,
           COALESCE(lib.in_library, 0) AS listen_library,
           COALESCE(lib.played, 0) AS listen_played,
           {sc_liked_sql("r.soundcloud_id")} AS listen_liked,
           slj.status AS sc_like_action
    FROM ranked r
    JOIN discovery_artists da ON da.id = r.artist_id
    LEFT JOIN lib ON lib.soundcloud_id = r.soundcloud_id
    LEFT JOIN pred ON pred.soundcloud_id = r.soundcloud_id
    LEFT JOIN sc_track_listens l ON l.soundcloud_id = r.soundcloud_id
    LEFT JOIN sc_like_job slj ON slj.soundcloud_id = r.soundcloud_id
    LEFT JOIN sc_track_decisions d
      ON d.soundcloud_id = r.soundcloud_id AND d.is_current = 1
    WHERE r.rn = 1 AND {not_flagged_sql("r.soundcloud_id")}
    ORDER BY r.artist_id
"""


def iso_z(moment: datetime) -> str:
    """Render an aware datetime as ISO 8601 UTC with a trailing Z."""
    return moment.astimezone(UTC).strftime(_ISO_Z)


def window_params(days: int, now: datetime) -> dict[str, str]:
    """The cutoff in each stored format: normalized ('...T..Z', what utc_iso()
    emits), SQLite default (seen_at) and SoundCloud's raw repost time."""
    if not MIN_DAYS <= days <= MAX_DAYS:
        raise ValueError(f"days must be {MIN_DAYS}..{MAX_DAYS}, got {days}")
    cutoff = (now - timedelta(days=days)).astimezone(UTC)
    return {
        "since": cutoff.strftime(_ISO_Z),
        "since_seen": cutoff.strftime("%Y-%m-%d %H:%M:%S"),
        "since_raw": cutoff.strftime("%Y/%m/%d %H:%M:%S"),
    }


def listened_via(row: Any) -> tuple[str, ...]:
    """Which listened signals fired for one row."""
    return tuple(src for src in LISTEN_SOURCES if row[f"listen_{src}"])


def row_to_track(row: Any) -> dict[str, Any]:
    """One contract track. Legacy 'hide' verdicts count as listened but have
    no contract value, so they surface as decision null."""
    decision = row["decision"]
    return {
        "soundcloud_id": row["soundcloud_id"],
        "title": row["title"],
        "artist_name": row["artist_name"],
        "artwork_url": row["artwork_url"],
        "permalink_url": row["permalink_url"],
        "duration_ms": row["duration_ms"] or 0,
        "kind": row["kind"],
        "activity_at": row["activity_at"],
        "local_track_id": row["local_track_id"],
        "score": row["score"],
        "decision": decision if decision in DECISIONS else None,
        "listened": bool(listened_via(row)),
        "sc_liked": bool(row["listen_liked"]),
        "sc_like_action": row["sc_like_action"],
    }


def score_sort_key(track: dict[str, Any]) -> tuple[bool, float]:
    """Score desc, unscored last."""
    score = track["score"]
    return (score is None, -(score or 0.0))


def sort_tracks(tracks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score desc (unscored last), ties broken by activity_at desc."""
    by_recent = sorted(tracks, key=lambda t: t["activity_at"], reverse=True)
    return sorted(by_recent, key=score_sort_key)  # stable: keeps recency order


def build_artist(rows: list[Any]) -> dict[str, Any]:
    """Group one artist's rows into the contract shape."""
    first = rows[0]
    tracks = sort_tracks([row_to_track(row) for row in rows])
    return {
        "discovery_artist_id": first["artist_id"],
        "display_name": first["display_name"],
        "slug": first["slug"],
        "avatar_url": first["avatar_url"],
        "latest_activity_at": max(t["activity_at"] for t in tracks),
        "unheard_count": sum(not t["listened"] for t in tracks),
        "tracks": tracks,
    }


def build_artists(rows: list[Any]) -> list[dict[str, Any]]:
    """Artists with something unheard, most recent activity first."""
    grouped = groupby(rows, key=lambda row: row["artist_id"])
    artists = [build_artist(list(artist_rows)) for _, artist_rows in grouped]
    active = [a for a in artists if a["unheard_count"] > 0]
    return sorted(
        active,
        key=lambda a: (a["latest_activity_at"], -a["discovery_artist_id"]),
        reverse=True,
    )


def fetch_story_rows(days: int = 7, now: datetime | None = None) -> list[Any]:
    """Raw per-(artist, track) rows for the window, ordered by artist id."""
    moment = now or datetime.now(UTC)
    with get_db_connection() as conn:
        return conn.execute(_STORIES_SQL, window_params(days, moment)).fetchall()


def get_stories(days: int = 7, now: datetime | None = None) -> dict[str, Any]:
    """The GET /api/stories payload."""
    moment = now or datetime.now(UTC)
    rows = fetch_story_rows(days, moment)
    return {"generated_at": iso_z(moment), "artists": build_artists(rows)}


def mark_listened(soundcloud_id: str, surface: str | None) -> None:
    """Idempotent: the first listen's timestamp and surface win."""
    with get_db_connection() as conn:
        conn.execute(
            """INSERT INTO sc_track_listens (soundcloud_id, surface)
               VALUES (?, ?) ON CONFLICT(soundcloud_id) DO NOTHING""",
            (soundcloud_id, surface),
        )
        conn.commit()
