"""Artist query functions for discovery_artists table."""

import sqlite3
from datetime import datetime, timezone
from typing import Any

from loguru import logger

# ---------------------------------------------------------------------------
# Artist stats CTE query
# ---------------------------------------------------------------------------

ARTISTS_STATS_SQL = """
WITH library_counts AS (
  SELECT amr.discovery_artist_id, COUNT(*) AS library_count
  FROM artist_match_resolved amr
  INNER JOIN tracks t ON t.artist_normalized = amr.local_name
  GROUP BY amr.discovery_artist_id
),
feed_stats AS (
  SELECT discovery_artist_id,
         COUNT(*) FILTER (WHERE seen_at > datetime('now', '-7 days')) / 7.0 AS noise_7d,
         COUNT(*) FILTER (WHERE seen_at > datetime('now', '-30 days')) / 30.0 AS noise_30d,
         MAX(seen_at) AS last_activity_at
  FROM sc_feed_events GROUP BY discovery_artist_id
),
repost_counts AS (
  SELECT dtr.discovery_artist_id, COUNT(DISTINCT t.id) AS repost_count
  FROM discovery_track_reposters dtr
  INNER JOIN discovery_tracks dt ON dt.id = dtr.discovery_track_id
  INNER JOIN tracks t ON t.soundcloud_id = dt.soundcloud_id
  GROUP BY dtr.discovery_artist_id
),
first_loved AS (
  SELECT amr.discovery_artist_id, t.id AS track_id, t.title, t.artist, r.timestamp AS loved_at
  FROM artist_match_resolved amr
  INNER JOIN tracks t ON t.artist_normalized = amr.local_name
  INNER JOIN ratings r ON r.track_id = t.id AND r.rating_type = 'love'
  WHERE r.timestamp = (
    SELECT MIN(r2.timestamp) FROM ratings r2
    INNER JOIN tracks t2 ON t2.id = r2.track_id
    WHERE t2.artist_normalized = amr.local_name AND r2.rating_type = 'love'
  )
  GROUP BY amr.discovery_artist_id
),
last_loved AS (
  SELECT amr.discovery_artist_id, MAX(r.timestamp) AS last_loved_at
  FROM artist_match_resolved amr
  INNER JOIN tracks t ON t.artist_normalized = amr.local_name
  INNER JOIN ratings r ON r.track_id = t.id AND r.rating_type = 'love'
  GROUP BY amr.discovery_artist_id
),
avg_elo AS (
  -- ELO is per-playlist; use global playlist ELO as a proxy (avg across all playlists)
  SELECT amr.discovery_artist_id, AVG(per.rating) AS avg_elo
  FROM artist_match_resolved amr
  INNER JOIN tracks t ON t.artist_normalized = amr.local_name
  INNER JOIN playlist_elo_ratings per ON per.track_id = t.id
  GROUP BY amr.discovery_artist_id
)
SELECT da.id, da.soundcloud_user_id, da.slug, da.display_name, da.avatar_url,
       da.follower_count, da.is_following, da.ranking, da.in_top_200,
       da.hit_rate, da.tracks_seen,
       COALESCE(lc.library_count, 0) AS library_track_count,
       COALESCE(rc.repost_count, 0) AS repost_in_library_count,
       COALESCE(fs.noise_7d, 0) AS feed_noise_7d,
       COALESCE(fs.noise_30d, 0) AS feed_noise_30d,
       fs.last_activity_at,
       fl.track_id AS first_loved_id, fl.title AS first_loved_title,
       fl.artist AS first_loved_artist, fl.loved_at AS first_loved_at,
       ll.last_loved_at,
       ae.avg_elo
FROM discovery_artists da
LEFT JOIN library_counts lc ON lc.discovery_artist_id = da.id
LEFT JOIN feed_stats fs ON fs.discovery_artist_id = da.id
LEFT JOIN repost_counts rc ON rc.discovery_artist_id = da.id
LEFT JOIN first_loved fl ON fl.discovery_artist_id = da.id
LEFT JOIN last_loved ll ON ll.discovery_artist_id = da.id
LEFT JOIN avg_elo ae ON ae.discovery_artist_id = da.id

UNION ALL

-- Local-only artists (tracks with artist_normalized that never resolves to a discovery_artists row)
SELECT NULL AS id, NULL, NULL, t.artist AS display_name, NULL,
       NULL, 0, NULL, 0, NULL, 0,
       COUNT(*) AS library_track_count,
       0, 0, 0, NULL,
       NULL, NULL, NULL, NULL,
       MAX(CASE WHEN r.rating_type = 'love' THEN r.timestamp END) AS last_loved_at,
       AVG(per.rating) AS avg_elo
FROM tracks t
LEFT JOIN ratings r ON r.track_id = t.id
LEFT JOIN playlist_elo_ratings per ON per.track_id = t.id
WHERE t.artist_normalized NOT IN (SELECT local_name FROM artist_match_resolved)
  AND t.artist_normalized IS NOT NULL
  AND t.artist_normalized != ''
GROUP BY t.artist_normalized
"""

# Sort ORDER BY clauses (appended to the CTE query)
_SORT_CLAUSES: dict[str, str] = {
    "name": "ORDER BY display_name COLLATE NOCASE ASC",
    "rank": "ORDER BY ranking ASC NULLS LAST, display_name COLLATE NOCASE ASC",
    "library": "ORDER BY library_track_count DESC, display_name COLLATE NOCASE ASC",
    "reposts": "ORDER BY repost_in_library_count DESC, display_name COLLATE NOCASE ASC",
    "hit_rate": "ORDER BY hit_rate DESC NULLS LAST, display_name COLLATE NOCASE ASC",
    "noise": "ORDER BY feed_noise_7d DESC, display_name COLLATE NOCASE ASC",
    "last_loved": "ORDER BY last_loved_at DESC NULLS LAST, display_name COLLATE NOCASE ASC",
}

# Source filter WHERE clauses (applied as outer wrapping query)
_SOURCE_FILTERS: dict[str, str] = {
    "soundcloud": "WHERE id IS NOT NULL",
    "local": "WHERE id IS NULL",
    "following": "WHERE is_following = 1",
    "all": "",
}


def _derive_activity_state(last_activity_at: str | None) -> str:
    """Derive activity_state from last_activity_at ISO string.

    active  = within 7 days
    silent  = 7–30 days
    dormant = older than 30 days or null
    """
    if not last_activity_at:
        return "dormant"
    try:
        last = datetime.fromisoformat(last_activity_at.replace("Z", "+00:00"))
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        delta_days = (now - last).total_seconds() / 86400
        if delta_days < 7:
            return "active"
        if delta_days < 30:
            return "silent"
        return "dormant"
    except (ValueError, TypeError):
        return "dormant"


def _build_first_loved(row: dict[str, Any]) -> dict[str, Any] | None:
    """Build nested first_loved_track object from flat row columns."""
    if row.get("first_loved_id") is None:
        return None
    return {
        "track_id": row["first_loved_id"],
        "title": row["first_loved_title"],
        "artist": row["first_loved_artist"],
        "loved_at": row["first_loved_at"],
    }


def _coerce_row(row: dict[str, Any]) -> dict[str, Any]:
    """Coerce raw SQLite row into ArtistStats shape."""
    return {
        "id": row["id"],
        "soundcloud_user_id": row["soundcloud_user_id"],
        "display_name": row["display_name"],
        "slug": row["slug"],
        "avatar_url": row["avatar_url"],
        "follower_count": row["follower_count"],
        "is_following": bool(row["is_following"]),
        "ranking": row["ranking"],
        "in_top_200": bool(row["in_top_200"]),
        "hit_rate": row["hit_rate"],
        "tracks_seen": row["tracks_seen"],
        "library_track_count": row["library_track_count"],
        "repost_in_library_count": row["repost_in_library_count"],
        "feed_noise_7d": row["feed_noise_7d"],
        "feed_noise_30d": row["feed_noise_30d"],
        "last_loved_at": row["last_loved_at"],
        "first_loved_track": _build_first_loved(row),
        "avg_elo": row["avg_elo"],
        "last_activity_at": row["last_activity_at"],
        "activity_state": _derive_activity_state(row.get("last_activity_at")),
    }


def get_artist_stats(
    conn: sqlite3.Connection,
    source: str = "all",
    sort: str = "name",
) -> list[dict[str, Any]]:
    """Return artist stats using the single CTE query.

    Args:
        conn: Open SQLite connection.
        source: Filter — 'all', 'soundcloud', 'local', or 'following'.
        sort: Sort key — 'name', 'rank', 'library', 'reposts',
              'hit_rate', 'noise', or 'last_loved'.

    Returns:
        List of ArtistStats dicts ready for JSON serialisation.
    """
    source_filter = _SOURCE_FILTERS.get(source, "")
    order_clause = _SORT_CLAUSES.get(sort, _SORT_CLAUSES["name"])

    if source_filter:
        # Wrap CTE in a subquery so we can filter on the aliased columns
        sql = (
            f"SELECT * FROM ({ARTISTS_STATS_SQL.strip()}) sub\n"
            f"{source_filter}\n"
            f"{order_clause}"
        )
    else:
        sql = f"{ARTISTS_STATS_SQL.strip()}\n{order_clause}"

    rows = conn.execute(sql).fetchall()
    return [_coerce_row(dict(r)) for r in rows]


def sync_followings(
    conn: sqlite3.Connection,
    followings: list[dict[str, Any]],
) -> dict[str, int]:
    """Upsert SoundCloud followings into discovery_artists.

    Strategy:
    1. Mark ALL currently is_following=1 rows as is_following=0.
    2. For each following: UPDATE if soundcloud_user_id matches, else INSERT.
    3. All done in a single transaction (caller must commit).

    Returns:
        {followings_synced, new_artists, unfollowed_remotely}
    """
    # Count artists that were following before sync
    cursor = conn.execute(
        "SELECT COUNT(*) FROM discovery_artists WHERE is_following = 1"
    )
    was_following_count: int = cursor.fetchone()[0]

    # Step 1: Reset all is_following flags
    conn.execute("UPDATE discovery_artists SET is_following = 0 WHERE is_following = 1")

    inserted = 0
    updated = 0

    for user in followings:
        sc_id = str(user.get("id", ""))
        username = user.get("permalink", "") or user.get("username", "") or sc_id
        display_name = user.get("full_name", "") or user.get("username", "") or username
        avatar_url: str | None = user.get("avatar_url")
        follower_count: int | None = user.get("followers_count")

        if not sc_id:
            logger.warning(f"sync_followings: skipping user with no id: {user}")
            continue

        # Check if artist exists by soundcloud_user_id
        row = conn.execute(
            "SELECT id FROM discovery_artists WHERE soundcloud_user_id = ?",
            (sc_id,),
        ).fetchone()

        if row:
            conn.execute(
                """
                UPDATE discovery_artists
                SET is_following = 1,
                    avatar_url = ?,
                    follower_count = ?,
                    display_name = ?,
                    last_sc_sync_at = CURRENT_TIMESTAMP
                WHERE soundcloud_user_id = ?
                """,
                (avatar_url, follower_count, display_name, sc_id),
            )
            updated += 1
        else:
            # Derive slug from username (permalink is the SC slug)
            slug = username.lower().strip()
            # Find a unique slug — append SC id suffix if collision
            existing_slug = conn.execute(
                "SELECT id FROM discovery_artists WHERE slug = ?", (slug,)
            ).fetchone()
            if existing_slug:
                slug = f"{slug}-{sc_id}"

            # New followings get a ranking at the end of the current list
            max_rank_row = conn.execute(
                "SELECT COALESCE(MAX(ranking), 0) FROM discovery_artists"
            ).fetchone()
            next_rank: int = max_rank_row[0] + 1

            conn.execute(
                """
                INSERT INTO discovery_artists
                    (soundcloud_user_id, slug, display_name, ranking,
                     avatar_url, follower_count, is_following, last_sc_sync_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                """,
                (sc_id, slug, display_name, next_rank, avatar_url, follower_count),
            )
            inserted += 1

    unfollowed_remotely = max(0, was_following_count - updated)

    logger.info(
        f"sync_followings: {len(followings)} fetched, "
        f"{updated} updated, {inserted} inserted, "
        f"{unfollowed_remotely} newly unfollowed"
    )

    return {
        "followings_synced": updated + inserted,
        "new_artists": inserted,
        "unfollowed_remotely": unfollowed_remotely,
    }
