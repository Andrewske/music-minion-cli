"""Artist query functions for discovery_artists table."""

import sqlite3
from typing import Any

from loguru import logger


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
