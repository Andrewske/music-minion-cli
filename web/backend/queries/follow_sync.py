"""Tier review: recent follows to confirm, and well-rated follows with no tier."""

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

_REVIEW_SELECT = f"""
SELECT id AS discovery_artist_id,
       COALESCE(display_name, slug) AS display_name,
       slug, avatar_url, NULLIF(tier, '') AS tier, followed_at, follow_order,
       {_RATED_COUNT_SQL} AS rated_count,
       {_KEEP_RATE_SQL} AS keep_rate
FROM discovery_artists
WHERE is_following = 1
"""

_UNTIERED = "COALESCE(tier, '') = ''"

# New follows get an automatic tier C (tier_auto = 1), so "recent" lists
# those too until Kevin picks a tier, which clears tier_auto.
_RECENT_SQL = f"""{_REVIEW_SELECT}
  AND ({_UNTIERED} OR tier_auto = 1)
  AND (followed_at IS NOT NULL OR follow_order IS NOT NULL)
ORDER BY followed_at IS NULL, followed_at DESC,
         follow_order IS NULL, follow_order ASC
LIMIT ?
"""

_RATED_SQL = f"""{_REVIEW_SELECT}
  AND {_UNTIERED}
  AND {_RATED_COUNT_SQL} >= ?
ORDER BY keep_rate DESC, rated_count DESC, discovery_artist_id
"""


def get_untiered_follows(conn: sqlite3.Connection) -> dict[str, list[dict[str, Any]]]:
    """Follows to tier, as {recent, rated}.

    recent: newest follows that are untiered or still on the automatic C
    (followed_at, then SC response position).
    rated: at least MIN_RATED_COUNT rated tracks, best keep rate first.
    """
    recent = conn.execute(_RECENT_SQL, (RECENT_LIMIT,)).fetchall()
    rated = conn.execute(_RATED_SQL, (MIN_RATED_COUNT,)).fetchall()
    return {"recent": [dict(r) for r in recent], "rated": [dict(r) for r in rated]}
