"""Untiered follows review: recent follows and well-rated follows with no tier."""

import sqlite3
from typing import Any

RECENT_LIMIT = 50
MIN_RATED_COUNT = 3

_RATED_COUNT_SQL = "(COALESCE(upload_rated_count, 0) + COALESCE(repost_rated_count, 0))"

# Role keep rates weighted by how many tracks each role has rated.
_KEEP_RATE_SQL = f"""(
  COALESCE(upload_keep_rate, 0) * COALESCE(upload_rated_count, 0)
  + COALESCE(repost_keep_rate, 0) * COALESCE(repost_rated_count, 0)
) / NULLIF({_RATED_COUNT_SQL}, 0)"""

_UNTIERED_SELECT = f"""
SELECT id AS discovery_artist_id,
       COALESCE(display_name, slug) AS display_name,
       slug, avatar_url, followed_at, follow_order,
       {_RATED_COUNT_SQL} AS rated_count,
       {_KEEP_RATE_SQL} AS keep_rate
FROM discovery_artists
WHERE is_following = 1 AND COALESCE(tier, '') = ''
"""

_RECENT_SQL = f"""{_UNTIERED_SELECT}
  AND (followed_at IS NOT NULL OR follow_order IS NOT NULL)
ORDER BY followed_at IS NULL, followed_at DESC,
         follow_order IS NULL, follow_order ASC
LIMIT ?
"""

_RATED_SQL = f"""{_UNTIERED_SELECT}
  AND {_RATED_COUNT_SQL} >= ?
ORDER BY keep_rate DESC, rated_count DESC, discovery_artist_id
"""


def get_untiered_follows(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    """Followed artists with no tier, as {recent, rated} for quick tiering.

    recent: newest follows first (followed_at, then SC response position).
    rated: at least MIN_RATED_COUNT rated tracks, best keep rate first.
    """
    recent = conn.execute(_RECENT_SQL, (RECENT_LIMIT,)).fetchall()
    rated = conn.execute(_RATED_SQL, (MIN_RATED_COUNT,)).fetchall()
    return {"recent": [dict(r) for r in recent], "rated": [dict(r) for r in rated]}
