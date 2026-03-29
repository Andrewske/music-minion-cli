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
        records.append((slug, tier, hit_rate, rank, tracks_seen, tracks_liked, tracks_dismissed))

    inserted = 0
    with get_db_connection() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO discovery_artists
                (slug, tier, hit_rate, ranking, tracks_seen, tracks_liked, tracks_dismissed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
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
    """Get all resolved artists ordered by ranking.

    If include_not_due is False (default), skip artists whose last_checked +
    check_interval_days > now (adaptive check intervals).
    """
    with get_db_connection() as conn:
        if include_not_due:
            cursor = conn.execute(
                """
                SELECT * FROM discovery_artists
                WHERE soundcloud_user_id IS NOT NULL
                ORDER BY ranking
                """
            )
        else:
            cursor = conn.execute(
                """
                SELECT * FROM discovery_artists
                WHERE soundcloud_user_id IS NOT NULL
                  AND (
                    last_checked IS NULL
                    OR datetime(last_checked, '+' || check_interval_days || ' days') <= datetime('now')
                  )
                ORDER BY ranking
                """
            )
        return [dict(row) for row in cursor.fetchall()]


def get_seen_track_ids() -> set[str]:
    """Get all SoundCloud track IDs that have been seen before (for dedup)."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT soundcloud_id FROM discovery_tracks")
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
        )
        for t in tracks
    ]

    with get_db_connection() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO discovery_tracks
                (soundcloud_id, slug, title, artist_name, duration_ms)
            VALUES (?, ?, ?, ?, ?)
            """,
            records,
        )
        conn.commit()
        return conn.total_changes


def insert_track_reposters(
    links: list[tuple[int, int, Optional[str]]]
) -> None:
    """Batch insert track-reposter relationships.

    Args:
        links: list of (discovery_track_id, discovery_artist_id, reposted_at_iso_or_None)
    """
    if not links:
        return

    with get_db_connection() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO discovery_track_reposters
                (discovery_track_id, discovery_artist_id, reposted_at)
            VALUES (?, ?, ?)
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

    Brackets:
    - No data (tracks_seen == 0): 3 slots
    - hit_rate > 40%: 8 slots
    - hit_rate 20-40%: 4 slots
    - hit_rate 5-20%: 2 slots
    - hit_rate < 5%: 1 slot

    Args:
        artists: list of artist dicts with 'id', 'hit_rate', and 'tracks_seen' keys

    Returns:
        dict mapping artist_id -> max_slots
    """
    def _slots(artist: dict[str, Any]) -> int:
        if not artist.get("tracks_seen"):
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
