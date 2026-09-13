"""Discovery query functions for SoundCloud reposts sync feature."""

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from music_minion.core.database import get_db_connection
from web.backend.artist_quality import (
    DEFAULT_PRIOR,
    rate_or_prior,
    recalculate_artist_role_stats,
)

# SQLite has a limit of 999 variables per query; use batches of 900 to be safe
_SQLITE_BATCH_SIZE = 900

# Discovery selection uses the live, editable ranking. The static ``in_top_200``
# seed flag is provenance only and must not gate selection or filtering.
DISCOVERY_MAX_RANK = 200

# Legacy discovery_tracks.status compatibility values. Preference labels now
# live only in sc_track_decisions; workflow_state owns playlist progression.
#   - 'unseen':      ingested but never classified; eligible for fetch/backfill
#   - 'in_playlist': placed in the discovery reposts playlist (awaiting decision)
#   - 'liked':       user kept it (added to a monthly/linked playlist)
#   - 'dismissed':   user passed; counts against the reposting artist's hit_rate
# Adding a new value here REQUIRES updating get_seen_track_ids()'s WHERE clause.
DISCOVERY_STATUSES: tuple[str, ...] = (
    "unseen",
    "in_playlist",
    "liked",
    "dismissed",
)


def _validate_status(status: str) -> None:
    """Reject unknown discovery_tracks.status values before any write.

    Guards existing DBs (which lack a CHECK constraint) against enum drift.
    """
    if status not in DISCOVERY_STATUSES:
        raise ValueError(
            f"Invalid discovery_tracks.status {status!r}; "
            f"valid values are {DISCOVERY_STATUSES}"
        )


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
        records.append(
            (
                slug,
                tier,
                hit_rate,
                rank,
                tracks_seen,
                tracks_liked,
                tracks_dismissed,
                in_top_200,
            )
        )

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

    logger.info(
        f"seed_artists_from_csv: inserted {inserted} of {len(records)} artists from {csv_path}"
    )
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


def get_ranked_artists(
    include_not_due: bool = False, max_rank: int | None = DISCOVERY_MAX_RANK
) -> list[dict[str, Any]]:
    """Get resolved, still-followed artists within the live ranking cutoff.

    ``in_top_200`` is retained only as seed provenance. Selection always uses
    the editable current ranking so rank changes take effect immediately.

    Args:
        include_not_due: If True, include artists not yet due for a check.
        max_rank: Current-rank cutoff; ``None`` means every followed artist.
    """
    with get_db_connection() as conn:
        rank_clause = "" if max_rank is None else "AND ranking <= ?"
        params: tuple[int, ...] = () if max_rank is None else (max_rank,)
        if include_not_due:
            cursor = conn.execute(
                f"""
                SELECT * FROM discovery_artists
                WHERE soundcloud_user_id IS NOT NULL
                  {rank_clause}
                  AND is_following = 1
                ORDER BY ranking
                """,
                params,
            )
        else:
            cursor = conn.execute(
                f"""
                SELECT * FROM discovery_artists
                WHERE soundcloud_user_id IS NOT NULL
                  {rank_clause}
                  AND is_following = 1
                  AND (
                    last_checked IS NULL
                    OR datetime(last_checked, '+' || check_interval_days || ' days') <= datetime('now')
                )
                ORDER BY ranking
                """,
                params,
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


def get_followed_artists_due_for_upload_check() -> list[dict[str, Any]]:
    """Get followed artists due under the independent upload cadence."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM discovery_artists
            WHERE is_following = 1
              AND soundcloud_user_id IS NOT NULL
              AND (
                uploads_last_checked IS NULL
                OR datetime(
                    uploads_last_checked,
                    '+' || COALESCE(upload_check_interval_hours, 24) || ' hours'
                ) <= datetime('now')
              )
            ORDER BY ranking IS NULL, ranking
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def get_seen_track_ids() -> set[str]:
    """SC IDs to exclude from fresh fetches: decided or already placed.

    Tracks with status='unseen' (incl. those ingested by sync_followings_reposts)
    remain eligible — the discovery sync should be free to re-encounter them and
    promote them to a playlist.

    Status coupling: if a new value is added to DISCOVERY_STATUSES,
    decide whether it belongs in this exclusion set too. See TODOS.md.
    """
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT dt.soundcloud_id FROM discovery_tracks dt
            WHERE dt.workflow_state IN ('in_playlist', 'processed')
               OR EXISTS (
                   SELECT 1 FROM sc_track_decisions d
                   WHERE d.soundcloud_id = dt.soundcloud_id AND d.is_current = 1
                     AND d.decision IN ('keep', 'nope')
               )
        """)
        return {row["soundcloud_id"] for row in cursor.fetchall()}


def insert_discovery_tracks(tracks: list[dict[str, Any]]) -> int:
    """Batch upsert discovery tracks and return the number newly inserted.

    Empty or absent metadata never erases a value learned from a richer API
    response. Every current SoundCloud sighting can therefore repair legacy
    discovery rows as well as insert new ones.
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
            t.get("uploader_soundcloud_id"),
            t.get("genre"),
            t.get("artwork_url"),
            t.get("permalink_url"),
            t.get("access"),
            t.get("uploaded_at"),
            t.get("released_at"),
            t.get("metadata_updated_at") or datetime.now(timezone.utc).isoformat(),
        )
        for t in tracks
    ]

    with get_db_connection() as conn:
        existing: set[str] = set()
        sc_ids = list({record[0] for record in records})
        for i in range(0, len(sc_ids), _SQLITE_BATCH_SIZE):
            batch = sc_ids[i : i + _SQLITE_BATCH_SIZE]
            placeholders = ",".join("?" * len(batch))
            rows = conn.execute(
                f"SELECT soundcloud_id FROM discovery_tracks "
                f"WHERE soundcloud_id IN ({placeholders})",
                batch,
            ).fetchall()
            existing.update(row["soundcloud_id"] for row in rows)

        conn.executemany(
            """
            INSERT INTO discovery_tracks
                (soundcloud_id, slug, title, artist_name, duration_ms,
                 uploader_soundcloud_id, genre, artwork_url, permalink_url,
                 access, uploaded_at, released_at, metadata_updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(soundcloud_id) DO UPDATE SET
                slug = COALESCE(NULLIF(excluded.slug, ''), discovery_tracks.slug),
                title = COALESCE(NULLIF(excluded.title, ''), discovery_tracks.title),
                artist_name = COALESCE(
                    NULLIF(excluded.artist_name, ''), discovery_tracks.artist_name
                ),
                duration_ms = CASE
                    WHEN excluded.duration_ms > 0 THEN excluded.duration_ms
                    ELSE discovery_tracks.duration_ms
                END,
                uploader_soundcloud_id = COALESCE(
                    excluded.uploader_soundcloud_id,
                    discovery_tracks.uploader_soundcloud_id
                ),
                genre = COALESCE(NULLIF(excluded.genre, ''), discovery_tracks.genre),
                artwork_url = COALESCE(
                    excluded.artwork_url, discovery_tracks.artwork_url
                ),
                permalink_url = COALESCE(
                    excluded.permalink_url, discovery_tracks.permalink_url
                ),
                access = COALESCE(excluded.access, discovery_tracks.access),
                uploaded_at = COALESCE(
                    excluded.uploaded_at, discovery_tracks.uploaded_at
                ),
                released_at = COALESCE(
                    excluded.released_at, discovery_tracks.released_at
                ),
                metadata_updated_at = excluded.metadata_updated_at
            """,
            records,
        )
        conn.commit()
        return len(set(sc_ids) - existing)


def insert_track_reposters(
    links: list[
        tuple[int, int, Optional[str]]
        | tuple[int, int, Optional[str], Optional[str], str]
    ],
) -> int:
    """Batch upsert repost events, tagged with seen_at=now.

    The three-item legacy form treats a non-NULL timestamp as exact. New
    ingestion should pass (track_id, actor_id, reposted_at, raw_reposted_at,
    precision), leaving reposted_at NULL when the repost endpoint only exposes
    the track's upload time.

    Returns the number of newly observed actor/track relationships.
    """
    if not links:
        return 0

    records: list[tuple[int, int, Optional[str], Optional[str], str]] = []
    for link in links:
        if len(link) == 3:
            track_id, artist_id, reposted_at = link
            precision = "exact" if reposted_at else "approximate"
            records.append((track_id, artist_id, reposted_at, reposted_at, precision))
            continue
        track_id, artist_id, reposted_at, raw_reposted_at, precision = link
        if precision not in ("exact", "approximate"):
            raise ValueError(f"Invalid repost timestamp precision: {precision!r}")
        records.append((track_id, artist_id, reposted_at, raw_reposted_at, precision))

    with get_db_connection() as conn:
        unique_pairs = {(record[0], record[1]) for record in records}
        existing_pairs: set[tuple[int, int]] = set()
        track_ids = list({pair[0] for pair in unique_pairs})
        for i in range(0, len(track_ids), _SQLITE_BATCH_SIZE):
            batch = track_ids[i : i + _SQLITE_BATCH_SIZE]
            placeholders = ",".join("?" * len(batch))
            rows = conn.execute(
                f"""SELECT discovery_track_id, discovery_artist_id
                FROM discovery_track_reposters
                WHERE discovery_track_id IN ({placeholders})""",
                batch,
            ).fetchall()
            existing_pairs.update(
                (row["discovery_track_id"], row["discovery_artist_id"]) for row in rows
            )
        conn.executemany(
            """
            INSERT INTO discovery_track_reposters
                (discovery_track_id, discovery_artist_id, reposted_at, seen_at,
                 event_type, raw_reposted_at, repost_time_precision)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, 'repost', ?, ?)
            ON CONFLICT(discovery_track_id, discovery_artist_id) DO UPDATE SET
                reposted_at = CASE
                    WHEN excluded.repost_time_precision = 'exact'
                    THEN excluded.reposted_at
                    ELSE discovery_track_reposters.reposted_at
                END,
                raw_reposted_at = COALESCE(
                    excluded.raw_reposted_at,
                    discovery_track_reposters.raw_reposted_at
                ),
                repost_time_precision = CASE
                    WHEN excluded.repost_time_precision = 'exact' THEN 'exact'
                    ELSE discovery_track_reposters.repost_time_precision
                END,
                event_type = 'repost'
            """,
            records,
        )
        conn.commit()
    return len(unique_pairs - existing_pairs)


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
    max_rank: int | None = DISCOVERY_MAX_RANK,
) -> list[dict[str, Any]]:
    """Get older discovery tracks that never made it to a playlist.

    Returns dicts shaped like SC API tracks so they work with
    _select_tracks_waterfall: {id, artist_id, artist_repost_keep_rate,
    created_at, duration}. Ordered by role-specific Bayesian keep rate then
    repost time, with NULL timestamps last.

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
                   dt.uploaded_at, dt.released_at,
                   dt.title, dt.artist_name,
                   best.discovery_artist_id, best.reposted_at,
                   da_best.repost_keep_rate AS artist_repost_keep_rate,
                   da_best.repost_rated_count AS artist_repost_rated_count
            FROM discovery_tracks dt
            JOIN (
                SELECT dtr.discovery_track_id,
                       dtr.discovery_artist_id,
                       dtr.reposted_at,
                       ROW_NUMBER() OVER (
                           PARTITION BY dtr.discovery_track_id
                           ORDER BY da.ranking IS NULL, da.ranking ASC
                       ) AS rn
                FROM discovery_track_reposters dtr
                JOIN discovery_artists da
                  ON da.id = dtr.discovery_artist_id
                 AND (? IS NULL OR da.ranking <= ?)
                 AND da.is_following = 1
            ) best ON best.discovery_track_id = dt.id AND best.rn = 1
            JOIN discovery_artists da_best ON da_best.id = best.discovery_artist_id
            WHERE dt.workflow_state = 'unseen'
              AND dt.duration_ms <= 600000
            ORDER BY COALESCE(da_best.repost_keep_rate, ?) DESC,
                     best.reposted_at IS NULL, best.reposted_at DESC
            LIMIT ?
            """,
            (max_rank, max_rank, DEFAULT_PRIOR, limit),
        ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        sc_id = row["soundcloud_id"]
        if sc_id in exclude_sc_ids:
            continue
        if sc_id in owned_sc_ids:
            continue
        results.append(
            {
                "id": sc_id,
                "artist_id": row["discovery_artist_id"],
                "artist_repost_keep_rate": rate_or_prior(
                    row["artist_repost_keep_rate"]
                ),
                "artist_repost_rated_count": row["artist_repost_rated_count"] or 0.0,
                "reposted_at": row["reposted_at"],
                "uploaded_at": row["uploaded_at"],
                "released_at": row["released_at"],
                "created_at": row["first_seen"] or "1970/01/01 00:00:00 +0000",
                "duration": row["duration_ms"],
                "title": row["title"] or "",
                "user": {"username": row["artist_name"] or "Unknown"},
            }
        )
    return results


def mark_tracks_in_playlist(sc_ids: list[str], batch_number: int) -> None:
    """Mark tracks as placed in the discovery playlist."""
    if not sc_ids:
        return

    status = "in_playlist"
    _validate_status(status)
    with get_db_connection() as conn:
        for i in range(0, len(sc_ids), _SQLITE_BATCH_SIZE):
            batch = sc_ids[i : i + _SQLITE_BATCH_SIZE]
            placeholders = ",".join("?" * len(batch))
            conn.execute(
                f"""
                UPDATE discovery_tracks
                SET status = ?, workflow_state = 'in_playlist', playlist_batch = ?
                WHERE soundcloud_id IN ({placeholders})
                """,
                [status, batch_number, *batch],
            )
        conn.commit()


def _set_track_status(sc_ids: list[str], status: str) -> None:
    """Batch-update discovery_tracks.status, validating against the constant."""
    _validate_status(status)
    if not sc_ids:
        return
    with get_db_connection() as conn:
        for i in range(0, len(sc_ids), _SQLITE_BATCH_SIZE):
            batch = sc_ids[i : i + _SQLITE_BATCH_SIZE]
            placeholders = ",".join("?" * len(batch))
            conn.execute(
                f"UPDATE discovery_tracks SET status = ? "
                f"WHERE soundcloud_id IN ({placeholders})",
                [status, *batch],
            )
        conn.commit()


def mark_tracks_liked(sc_ids: list[str], surface: str = "repost_builder") -> None:
    """Record canonical keep decisions (default surface: the repost builder)."""
    from web.backend.queries.feed import record_decisions

    record_decisions(sc_ids, "keep", surface)


def mark_tracks_dismissed(sc_ids: list[str]) -> None:
    """Record canonical nope decisions from the repost builder."""
    from web.backend.queries.feed import record_decisions

    record_decisions(sc_ids, "nope", "repost_builder")


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
                f"UPDATE discovery_tracks SET status = 'unseen', "
                f"workflow_state = 'unseen' WHERE soundcloud_id IN ({placeholders})",
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


def update_artist_uploads_last_checked(artist_id: int) -> None:
    """Advance only the upload checkpoint for one successfully fetched artist."""
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE discovery_artists
            SET uploads_last_checked = datetime('now')
            WHERE id = ?
            """,
            (artist_id,),
        )
        conn.commit()


def recalculate_artist_stats(artist_id: int | None = None) -> None:
    """Recalculate legacy display counters and the role-specific keep rates.

    Legacy columns (tracks_seen, tracks_liked, tracks_dismissed, hit_rate)
    give every actor full credit for every track and are kept for the UI
    only. Each artist/track pair is counted once even when that artist both
    uploaded and reposted it, and only canonical current keep/nope decisions
    from ``sc_track_decisions`` count; hide is deliberately absent.
    hit_rate = liked / max(1, liked + dismissed) * 100

    Selection reads ``upload_keep_rate`` / ``repost_keep_rate`` instead,
    which :func:`recalculate_artist_role_stats` refreshes for all artists.

    Pass artist_id for a targeted single-artist recalc of the legacy counters
    (feed rate endpoint); role stats are always refreshed globally because a
    track decision changes the fractional credit of every reposter on it.
    """
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            WITH contributions AS (
                SELECT dtr.discovery_artist_id AS artist_id, dt.soundcloud_id
                FROM discovery_track_reposters dtr
                JOIN discovery_tracks dt ON dt.id = dtr.discovery_track_id
                UNION
                SELECT u.discovery_artist_id, u.soundcloud_id
                FROM sc_artist_uploads u
            ), labeled AS (
                SELECT c.artist_id, c.soundcloud_id, d.decision
                FROM contributions c
                JOIN sc_track_decisions d
                  ON d.soundcloud_id = c.soundcloud_id AND d.is_current = 1
            )
            SELECT
                da.id,
                COUNT(l.soundcloud_id) AS tracks_seen,
                COALESCE(SUM(CASE WHEN l.decision = 'keep' THEN 1 ELSE 0 END), 0)
                    AS tracks_liked,
                COALESCE(SUM(CASE WHEN l.decision = 'nope' THEN 1 ELSE 0 END), 0)
                    AS tracks_dismissed
            FROM discovery_artists da
            LEFT JOIN labeled l ON l.artist_id = da.id
            WHERE (? IS NULL OR da.id = ?)
            GROUP BY da.id
            """,
            (artist_id, artist_id),
        ).fetchall()

        records = [
            (
                row["tracks_seen"],
                row["tracks_liked"],
                row["tracks_dismissed"],
                row["tracks_liked"]
                / max(1, row["tracks_liked"] + row["tracks_dismissed"])
                * 100,
                row["id"],
            )
            for row in rows
        ]

        conn.executemany(
            """
            UPDATE discovery_artists
            SET tracks_seen = ?, tracks_liked = ?, tracks_dismissed = ?, hit_rate = ?
            WHERE id = ?
            """,
            records,
        )
        recalculate_artist_role_stats(conn)
        conn.commit()
    logger.info(f"recalculate_artist_stats: updated {len(records)} artists")


def compute_slot_caps(artists: list[dict[str, Any]]) -> dict[int, int]:
    """Compute round-robin slot caps from reposter-only recommendation quality.

    Pure function (no DB access).

    ``repost_rated_count`` is the fractional track-level attribution count.
    Tracks that were fetched but never judged do not count.

    Brackets (Bayesian-smoothed repost keep rate):
    - No rated repost credit: 3 slots (benefit of doubt)
    - rate > 40%: 8 slots
    - rate 20-40%: 4 slots
    - rate 5-20%: 2 slots
    - rate < 5%: 1 slot

    Args:
        artists: list of artist dicts with ``id``, ``repost_keep_rate`` and
                 ``repost_rated_count`` keys

    Returns:
        dict mapping artist_id -> max_slots
    """

    def _slots(artist: dict[str, Any]) -> int:
        rated = artist.get("repost_rated_count") or 0
        if rated == 0:
            return 3
        rate = rate_or_prior(artist.get("repost_keep_rate")) * 100
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
