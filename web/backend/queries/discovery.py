"""Discovery query functions for SoundCloud reposts sync feature."""

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from music_minion.core.database import get_db_connection

# SQLite has a limit of 999 variables per query; use batches of 900 to be safe
_SQLITE_BATCH_SIZE = 900

_TIER_PRIORITY: dict[str, int] = {"S": 1, "A": 2, "B": 3, "C": 4, "D": 5}


def seed_artists_from_csv(csv_path: str) -> int:
    """Import artists from artist_tiers.csv into discovery_artists.

    CSV columns: artist_slug, tier, total_tracks, top_200_overlap, liked,
    not_interested, not_quite, unevaluated, quality_score, hit_rate,
    not_quite_rate, in_top_200

    Ranking: ordered by tier (S=1, A=2, B=3, C=4, D=5, empty=6) then by
    hit_rate descending within each tier.

    Returns count of artists inserted.
    """
    path = Path(csv_path)
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            rows.append(row)

    def _tier_key(row: dict[str, str]) -> tuple[int, float]:
        tier = row.get("tier", "").strip()
        priority = _TIER_PRIORITY.get(tier, 6)
        try:
            hit_rate = float(row.get("hit_rate", 0) or 0)
        except (ValueError, TypeError):
            hit_rate = 0.0
        return (priority, -hit_rate)

    rows.sort(key=_tier_key)

    records: list[tuple[str, str, float, int, int, int, int]] = []
    for rank, row in enumerate(rows, start=1):
        slug = row.get("artist_slug", "").strip()
        if not slug:
            continue
        tier = row.get("tier", "").strip()
        try:
            hit_rate = float(row.get("hit_rate", 0) or 0)
        except (ValueError, TypeError):
            hit_rate = 0.0
        try:
            tracks_seen = int(row.get("total_tracks", 0) or 0)
        except (ValueError, TypeError):
            tracks_seen = 0
        try:
            tracks_liked = int(row.get("liked", 0) or 0)
        except (ValueError, TypeError):
            tracks_liked = 0
        try:
            not_interested = int(row.get("not_interested", 0) or 0)
        except (ValueError, TypeError):
            not_interested = 0
        try:
            not_quite = int(row.get("not_quite", 0) or 0)
        except (ValueError, TypeError):
            not_quite = 0
        tracks_dismissed = not_interested + not_quite
        in_top_200 = 1 if row.get("in_top_200", "").strip() == "True" else 0
        records.append((slug, tier, hit_rate, rank, tracks_seen, tracks_liked, tracks_dismissed, in_top_200))

    inserted = 0
    with get_db_connection() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO discovery_artists
                (slug, tier, hit_rate, ranking, tracks_seen, tracks_liked, tracks_dismissed, in_top_200)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            records,
        )
        conn.commit()
        inserted = conn.total_changes

    logger.info(f"seed_artists_from_csv: inserted {inserted} of {len(records)} artists from {csv_path}")
    return inserted


def get_artists_needing_resolution() -> list[dict[str, Any]]:
    """Get artists whose SC user ID hasn't been resolved yet."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id, slug FROM discovery_artists WHERE soundcloud_user_id IS NULL ORDER BY ranking"
        )
        return [dict(row) for row in cursor.fetchall()]


def update_artist_sc_id(slug: str, sc_user_id: str, display_name: str) -> None:
    """Update an artist's SoundCloud user ID after resolution."""
    with get_db_connection() as conn:
        conn.execute(
            "UPDATE discovery_artists SET soundcloud_user_id = ?, display_name = ? WHERE slug = ?",
            (sc_user_id, display_name, slug),
        )
        conn.commit()


def get_ranked_artists(include_not_due: bool = False) -> list[dict[str, Any]]:
    """Get resolved top-200 artists ordered by ranking.

    Args:
        include_not_due: If True, include artists not yet due for a check.
    """
    with get_db_connection() as conn:
        if include_not_due:
            cursor = conn.execute(
                """
                SELECT * FROM discovery_artists
                WHERE soundcloud_user_id IS NOT NULL
                  AND in_top_200 = 1
                ORDER BY ranking
                """
            )
        else:
            cursor = conn.execute(
                """
                SELECT * FROM discovery_artists
                WHERE soundcloud_user_id IS NOT NULL
                  AND in_top_200 = 1
                  AND (
                    last_checked IS NULL
                    OR datetime(last_checked, '+' || check_interval_days || ' days') <= datetime('now')
                  )
                ORDER BY ranking
                """
            )
        return [dict(row) for row in cursor.fetchall()]


def get_followed_artists_due_for_check() -> list[dict[str, Any]]:
    """Get followed artists due for a repost check.

    Like get_ranked_artists() but filters by is_following=1 instead of
    in_top_200=1. Applies the same adaptive cadence: artists whose
    last_checked + check_interval_days <= now are returned.

    Used by the feed-noise daemon to track all followings, not just
    top-200 ranked artists.
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM discovery_artists
            WHERE is_following = 1
              AND soundcloud_user_id IS NOT NULL
              AND (
                last_checked IS NULL
                OR datetime(last_checked, '+' || COALESCE(check_interval_days, 1) || ' days') <= datetime('now')
              )
            ORDER BY ranking IS NULL, ranking
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def get_seen_track_ids() -> set[str]:
    """SC IDs to exclude from fresh fetches: classified or already placed.

    Tracks with status='unseen' (incl. those ingested by sync_followings_reposts)
    remain eligible — the discovery sync should be free to re-encounter them and
    promote them to a playlist.

    Status coupling: if a new value is added to discovery_tracks.status,
    update this WHERE clause too. See TODOS.md.
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT soundcloud_id FROM discovery_tracks "
            "WHERE status IN ('liked', 'dismissed', 'in_playlist')"
        )
        return {row["soundcloud_id"] for row in cursor.fetchall()}


def insert_discovery_tracks(tracks: list[dict[str, Any]]) -> int:
    """Batch insert new discovery tracks. Returns count inserted.

    Each track dict should have: soundcloud_id, slug, title, artist_name, duration_ms
    Uses INSERT OR IGNORE (soundcloud_id is UNIQUE).
    """
    if not tracks:
        return 0

    records = [
        (
            t["soundcloud_id"],
            t.get("slug", ""),
            t.get("title", ""),
            t.get("artist_name", ""),
            t.get("duration_ms", 0),
            t.get("released_at"),
        )
        for t in tracks
    ]

    with get_db_connection() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO discovery_tracks
                (soundcloud_id, slug, title, artist_name, duration_ms, released_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            records,
        )
        conn.commit()
        return conn.total_changes


def insert_track_reposters(
    links: list[tuple[int, int, Optional[str]]]
) -> None:
    """Batch insert track-reposter relationships, tagged with seen_at=now.

    INSERT OR IGNORE preserves first-observation seen_at for existing rows.

    Args:
        links: list of (discovery_track_id, discovery_artist_id, reposted_at_iso_or_None)
    """
    if not links:
        return

    with get_db_connection() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO discovery_track_reposters
                (discovery_track_id, discovery_artist_id, reposted_at, seen_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            links,
        )
        conn.commit()


def get_discovery_track_ids_by_sc_ids(sc_ids: list[str]) -> dict[str, int]:
    """Map SoundCloud IDs to discovery_tracks.id.

    Returns dict of {soundcloud_id: discovery_track_id}.
    """
    if not sc_ids:
        return {}

    result: dict[str, int] = {}
    with get_db_connection() as conn:
        for i in range(0, len(sc_ids), _SQLITE_BATCH_SIZE):
            batch = sc_ids[i : i + _SQLITE_BATCH_SIZE]
            placeholders = ",".join("?" * len(batch))
            cursor = conn.execute(
                f"SELECT id, soundcloud_id FROM discovery_tracks WHERE soundcloud_id IN ({placeholders})",
                batch,
            )
            for row in cursor.fetchall():
                result[row["soundcloud_id"]] = row["id"]
    return result


def get_artist_id_by_slug(slug: str) -> Optional[int]:
    """Get discovery_artist.id by slug."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id FROM discovery_artists WHERE slug = ?", (slug,)
        )
        row = cursor.fetchone()
        return row["id"] if row else None


def get_next_batch_number() -> int:
    """Get next playlist batch number."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT COALESCE(MAX(playlist_batch), 0) + 1 AS next_batch FROM discovery_tracks"
        )
        row = cursor.fetchone()
        return row["next_batch"] if row else 1


def get_owned_sc_ids(exclude_playlist_id: int) -> set[str]:
    """SC IDs the user already has on this device.

    Returns the union of (a) SC IDs of tracks in any playlist except
    `exclude_playlist_id`, and (b) SC IDs of tracks rated 'love'.

    Used to keep the discovery surface fresh: the reposts playlist should
    never re-recommend a track the user already filed away or loves.
    """
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT t.soundcloud_id
            FROM tracks t
            WHERE t.soundcloud_id IS NOT NULL
              AND (
                t.id IN (
                    SELECT track_id FROM playlist_tracks WHERE playlist_id != ?
                )
                OR t.id IN (
                    SELECT track_id FROM ratings WHERE rating_type = 'love'
                )
              )
            """,
            (exclude_playlist_id,),
        ).fetchall()
        return {row["soundcloud_id"] for row in rows}


def get_unplaced_short_tracks(
    exclude_sc_ids: set[str] | None = None,
    owned_sc_ids: set[str] | None = None,
    limit: int = 20000,
) -> list[dict[str, Any]]:
    """Get older discovery tracks that never made it to a playlist.

    Returns dicts shaped like SC API tracks so they work with
    _select_tracks_waterfall: {id, artist_id, artist_hit_rate, created_at, duration}.
    Ordered by hit_rate DESC, reposted_at DESC, NULLs last.

    Args:
        exclude_sc_ids: SC IDs already selected this run (avoid dupes).
        owned_sc_ids: SC IDs the user already has (other playlists, love-rated).
        limit: max rows to fetch from the DB.
    """
    if exclude_sc_ids is None:
        exclude_sc_ids = set()
    if owned_sc_ids is None:
        owned_sc_ids = set()
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT dt.soundcloud_id, dt.duration_ms, dt.first_seen,
                   dt.title, dt.artist_name,
                   best.discovery_artist_id, best.reposted_at,
                   da_best.hit_rate AS artist_hit_rate
            FROM discovery_tracks dt
            JOIN (
                SELECT dtr.discovery_track_id,
                       dtr.discovery_artist_id,
                       dtr.reposted_at,
                       ROW_NUMBER() OVER (
                           PARTITION BY dtr.discovery_track_id
                           ORDER BY da.ranking ASC
                       ) AS rn
                FROM discovery_track_reposters dtr
                JOIN discovery_artists da
                  ON da.id = dtr.discovery_artist_id
                 AND da.in_top_200 = 1
            ) best ON best.discovery_track_id = dt.id AND best.rn = 1
            JOIN discovery_artists da_best ON da_best.id = best.discovery_artist_id
            WHERE dt.status = 'unseen'
              AND dt.duration_ms <= 600000
              AND (best.reposted_at IS NULL
                   OR best.reposted_at > datetime('now', '-1 year'))
            ORDER BY da_best.hit_rate DESC, best.reposted_at IS NULL, best.reposted_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        sc_id = row["soundcloud_id"]
        if sc_id in exclude_sc_ids:
            continue
        if sc_id in owned_sc_ids:
            continue
        results.append({
            "id": sc_id,
            "artist_id": row["discovery_artist_id"],
            "artist_hit_rate": row["artist_hit_rate"] or 0.0,
            "reposted_at": row["reposted_at"],
            "created_at": row["first_seen"] or "1970/01/01 00:00:00 +0000",
            "duration": row["duration_ms"],
            "title": row["title"] or "",
            "user": {"username": row["artist_name"] or "Unknown"},
        })
    return results


def mark_tracks_in_playlist(sc_ids: list[str], batch_number: int) -> None:
    """Mark tracks as placed in the discovery playlist."""
    if not sc_ids:
        return

    with get_db_connection() as conn:
        for i in range(0, len(sc_ids), _SQLITE_BATCH_SIZE):
            batch = sc_ids[i : i + _SQLITE_BATCH_SIZE]
            placeholders = ",".join("?" * len(batch))
            conn.execute(
                f"""
                UPDATE discovery_tracks
                SET status = 'in_playlist', playlist_batch = ?
                WHERE soundcloud_id IN ({placeholders})
                """,
                [batch_number, *batch],
            )
        conn.commit()


def mark_tracks_liked(sc_ids: list[str]) -> None:
    """Mark tracks as liked (user added to monthly playlist)."""
    if not sc_ids:
        return

    with get_db_connection() as conn:
        for i in range(0, len(sc_ids), _SQLITE_BATCH_SIZE):
            batch = sc_ids[i : i + _SQLITE_BATCH_SIZE]
            placeholders = ",".join("?" * len(batch))
            conn.execute(
                f"UPDATE discovery_tracks SET status = 'liked' WHERE soundcloud_id IN ({placeholders})",
                batch,
            )
        conn.commit()


def mark_tracks_dismissed(sc_ids: list[str]) -> None:
    """Mark tracks as dismissed (user passed)."""
    if not sc_ids:
        return

    with get_db_connection() as conn:
        for i in range(0, len(sc_ids), _SQLITE_BATCH_SIZE):
            batch = sc_ids[i : i + _SQLITE_BATCH_SIZE]
            placeholders = ",".join("?" * len(batch))
            conn.execute(
                f"UPDATE discovery_tracks SET status = 'dismissed' WHERE soundcloud_id IN ({placeholders})",
                batch,
            )
        conn.commit()


def mark_tracks_unseen(sc_ids: list[str]) -> None:
    """Reset tracks to unseen (undecided tracks wiped from discovery inbox).

    Makes them eligible for fresh-fetch and the backfill pool again, without
    counting as a dismissal against the reposting artist's hit_rate.
    """
    if not sc_ids:
        return

    with get_db_connection() as conn:
        for i in range(0, len(sc_ids), _SQLITE_BATCH_SIZE):
            batch = sc_ids[i : i + _SQLITE_BATCH_SIZE]
            placeholders = ",".join("?" * len(batch))
            conn.execute(
                f"UPDATE discovery_tracks SET status = 'unseen' WHERE soundcloud_id IN ({placeholders})",
                batch,
            )
        conn.commit()


def update_artist_last_checked(artist_id: int, new_repost_count: int) -> None:
    """Update artist's last_checked timestamp and adaptive interval.

    If new_repost_count == 0: double check_interval_days (cap at 30)
    If new_repost_count > 0: reset check_interval_days to 1
    """
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE discovery_artists
            SET last_checked = datetime('now'),
                check_interval_days = CASE
                    WHEN ? > 0 THEN 1
                    ELSE MIN(check_interval_days * 2, 30)
                END
            WHERE id = ?
            """,
            (new_repost_count, artist_id),
        )
        conn.commit()


def recalculate_artist_stats() -> None:
    """Recalculate hit_rate, tracks_seen, tracks_liked, tracks_dismissed for all artists.

    Joins discovery_track_reposters -> discovery_tracks to count by status.
    hit_rate = liked / max(1, liked + dismissed) * 100
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                da.id,
                COUNT(*) AS tracks_seen,
                SUM(CASE WHEN dt.status = 'liked' THEN 1 ELSE 0 END) AS tracks_liked,
                SUM(CASE WHEN dt.status = 'dismissed' THEN 1 ELSE 0 END) AS tracks_dismissed
            FROM discovery_artists da
            JOIN discovery_track_reposters dtr ON dtr.discovery_artist_id = da.id
            JOIN discovery_tracks dt ON dt.id = dtr.discovery_track_id
            GROUP BY da.id
            """
        )
        stats = cursor.fetchall()

        records = [
            (
                row["tracks_seen"],
                row["tracks_liked"],
                row["tracks_dismissed"],
                row["tracks_liked"] / max(1, row["tracks_liked"] + row["tracks_dismissed"]) * 100,
                row["id"],
            )
            for row in stats
        ]

        conn.executemany(
            """
            UPDATE discovery_artists
            SET tracks_seen = ?, tracks_liked = ?, tracks_dismissed = ?, hit_rate = ?
            WHERE id = ?
            """,
            records,
        )
        conn.commit()
    logger.info(f"recalculate_artist_stats: updated {len(records)} artists")


def compute_slot_caps(artists: list[dict[str, Any]]) -> dict[int, int]:
    """Compute round-robin slot caps based on hit rate.

    Pure function (no DB access).

    "Rated" means tracks the user actually heard and judged (liked + dismissed).
    Tracks that were fetched but never shown don't count.

    Brackets:
    - No rated tracks (liked + dismissed == 0): 3 slots (benefit of doubt)
    - hit_rate > 40%: 8 slots
    - hit_rate 20-40%: 4 slots
    - hit_rate 5-20%: 2 slots
    - hit_rate < 5%: 1 slot

    Args:
        artists: list of artist dicts with 'id', 'hit_rate', 'tracks_liked',
                 'tracks_dismissed' keys

    Returns:
        dict mapping artist_id -> max_slots
    """
    def _slots(artist: dict[str, Any]) -> int:
        rated = (artist.get("tracks_liked") or 0) + (artist.get("tracks_dismissed") or 0)
        if rated == 0:
            return 3
        rate = artist.get("hit_rate", 0.0) or 0.0
        if rate > 40:
            return 8
        if rate > 20:
            return 4
        if rate >= 5:
            return 2
        return 1

    return {a["id"]: _slots(a) for a in artists}


def get_discovery_playlist_id(source: str = "soundcloud_reposts") -> Optional[int]:
    """Get playlist ID for a discovery source."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id FROM playlists WHERE discovery_source = ?", (source,)
        )
        row = cursor.fetchone()
        return row["id"] if row else None


def get_mixes_playlist_id() -> Optional[int]:
    """Get the mixes playlist ID."""
    return get_discovery_playlist_id("soundcloud_mixes")


def log_sync_run(
    started_at: datetime,
    artists_checked: int = 0,
    tracks_fetched: int = 0,
    tracks_added: int = 0,
    mixes_added: int = 0,
    tracks_skipped: int = 0,
    dry_run: bool = False,
    duration_seconds: float = 0.0,
) -> int:
    """Log a sync run to discovery_sync_log. Returns the log entry ID."""
    started_iso = started_at.isoformat()
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO discovery_sync_log
                (started_at, completed_at, artists_checked, tracks_fetched,
                 tracks_added, mixes_added, tracks_skipped, dry_run, duration_seconds)
            VALUES (?, datetime('now'), ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                started_iso,
                artists_checked,
                tracks_fetched,
                tracks_added,
                mixes_added,
                tracks_skipped,
                dry_run,
                duration_seconds,
            ),
        )
        conn.commit()
        return cursor.lastrowid  # type: ignore[return-value]


def get_last_sync() -> Optional[dict[str, Any]]:
    """Get the most recent sync log entry."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM discovery_sync_log ORDER BY started_at DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_resolution_status() -> dict[str, int]:
    """Get artist resolution status counts."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN soundcloud_user_id IS NOT NULL THEN 1 ELSE 0 END), 0) AS resolved,
                COALESCE(SUM(CASE WHEN soundcloud_user_id IS NULL THEN 1 ELSE 0 END), 0) AS pending
            FROM discovery_artists
            """
        )
        row = cursor.fetchone()
        return dict(row) if row else {"total": 0, "resolved": 0, "pending": 0}
