"""DB reads and writes behind GET /api/unfollow-suggestions.

Scoring is pure (web/backend/unfollow_suggestions.py); this module turns
tables into its inputs and records keeps.
"""

import sqlite3
from datetime import UTC, datetime
from typing import Any

from web.backend.queries.artists import set_artist_tier
from web.backend.soundcloud_metadata import parse_soundcloud_datetime as parse_time
from web.backend.unfollow_suggestions import (
    FollowedAccount,
    GoodItem,
    build_sections,
    latest,
)

# Each column keeps one timestamp format, so MAX per column is safe;
# latest() compares across formats.
_ACCOUNTS_SQL = """
    WITH reposts AS (
        SELECT discovery_artist_id AS artist_id, COUNT(*) AS n,
               MAX(reposted_at) AS last_reposted, MAX(seen_at) AS last_seen
        FROM discovery_track_reposters GROUP BY discovery_artist_id
    ),
    uploads AS (
        SELECT discovery_artist_id AS artist_id, COUNT(*) AS n,
               MAX(uploaded_at) AS last_uploaded
        FROM sc_artist_uploads GROUP BY discovery_artist_id
    )
    SELECT da.id, da.soundcloud_user_id, da.display_name, da.slug,
           da.avatar_url, da.follower_count, da.tier, da.followed_at,
           da.uploads_last_checked IS NOT NULL AS polled,
           COALESCE(r.n, 0) AS reposts, COALESCE(u.n, 0) AS uploads,
           r.last_reposted, r.last_seen, u.last_uploaded
    FROM discovery_artists da
    LEFT JOIN reposts r ON r.artist_id = da.id
    LEFT JOIN uploads u ON u.artist_id = da.id
    WHERE da.is_following = 1
      AND da.id NOT IN (SELECT discovery_artist_id FROM unfollow_suggestion_keeps)
"""

# Liked or kept tracks every followed account reposted or uploaded, with the
# like (or keep) time for recency.
_GOOD_ITEMS_SQL = """
    WITH good AS (
        SELECT soundcloud_id FROM sc_likes
        UNION
        SELECT soundcloud_id FROM sc_track_decisions
        WHERE is_current = 1 AND decision = 'keep'
    ),
    items AS (
        SELECT r.discovery_artist_id AS artist_id, dt.soundcloud_id,
               'repost' AS kind, COALESCE(r.reposted_at, r.seen_at) AS item_at
        FROM discovery_track_reposters r
        JOIN discovery_tracks dt ON dt.id = r.discovery_track_id
        WHERE dt.soundcloud_id IN good
        UNION ALL
        SELECT discovery_artist_id, soundcloud_id, 'upload', uploaded_at
        FROM sc_artist_uploads WHERE soundcloud_id IN good
    )
    SELECT i.artist_id, i.soundcloud_id, i.kind, i.item_at,
           CASE WHEN l.soundcloud_id IS NOT NULL THEN l.liked_at
                ELSE d.decided_at END AS liked_at,
           l.like_order
    FROM items i
    JOIN discovery_artists da ON da.id = i.artist_id AND da.is_following = 1
    LEFT JOIN sc_likes l ON l.soundcloud_id = i.soundcloud_id
    LEFT JOIN sc_track_decisions d ON d.soundcloud_id = i.soundcloud_id
        AND d.is_current = 1 AND d.decision = 'keep'
"""


def _account(r: sqlite3.Row) -> FollowedAccount:
    sc_id = r["soundcloud_user_id"]
    return FollowedAccount(
        discovery_artist_id=r["id"],
        soundcloud_user_id=str(sc_id) if sc_id else None,
        display_name=r["display_name"],
        slug=r["slug"],
        avatar_url=r["avatar_url"],
        followers=r["follower_count"],
        tier=r["tier"],
        followed_at=r["followed_at"],
        polled=bool(r["polled"]),
        reposts=r["reposts"],
        uploads=r["uploads"],
        last_item_at=latest((r["last_reposted"], r["last_seen"], r["last_uploaded"])),
    )


def load_accounts(conn: sqlite3.Connection) -> list[FollowedAccount]:
    """Followed accounts Kevin has not kept, with feed counts."""
    return [_account(r) for r in conn.execute(_ACCOUNTS_SQL)]


def load_good_items(conn: sqlite3.Connection) -> list[GoodItem]:
    """Liked/kept tracks in the feed, one row per followed account carrying it."""
    return [GoodItem(*r) for r in conn.execute(_GOOD_ITEMS_SQL)]


def feed_start(conn: sqlite3.Connection) -> datetime:
    """When the feed history began: the first repost seen."""
    first = conn.execute(
        "SELECT MIN(seen_at) FROM discovery_track_reposters"
    ).fetchone()[0]
    return parse_time(first) or datetime.now(UTC)


def compute_sections(
    conn: sqlite3.Connection, now: datetime | None = None
) -> dict[str, list[dict[str, Any]]]:
    return build_sections(
        load_accounts(conn),
        load_good_items(conn),
        feed_start(conn),
        now or datetime.now(UTC),
    )


def keep(conn: sqlite3.Connection, discovery_artist_id: int) -> bool:
    """Never suggest this account again; an untiered one becomes tier C.

    Returns False if the artist does not exist.
    """
    row = conn.execute(
        "SELECT tier FROM discovery_artists WHERE id = ?", (discovery_artist_id,)
    ).fetchone()
    if row is None:
        return False
    if row["tier"] is None:
        set_artist_tier(conn, discovery_artist_id, "C")
    conn.execute(
        """INSERT INTO unfollow_suggestion_keeps (discovery_artist_id) VALUES (?)
        ON CONFLICT(discovery_artist_id) DO NOTHING""",
        (discovery_artist_id,),
    )
    conn.commit()
    return True
