"""One track-level keep/nope decision per SoundCloud track.

Labels come from the canonical decision ledger (``sc_track_decisions``):
the single current row per track, ``keep`` -> 1, ``nope`` -> 0. ``hide`` is
a workflow choice, never a label, so hidden tracks are excluded. Track
metadata, uploader resolution and reposter events are joined in from
``discovery_tracks`` / ``sc_artist_uploads``; the legacy ``status`` columns
are never consulted.

Both the artist-quality aggregation (#60) and the offline keep-model dataset
(#61) read from here.

Decision timestamps
-------------------
``sc_track_decisions.decided_at`` is authoritative for rows written by the
live surfaces (``upload_feed``, ``repost_builder``): they stamp the real UTC
instant. The v62 migration, however, backfilled legacy labels with the best
timestamp it had, which is only sometimes a decision time:

- ``upload_feed_migration`` rows carry ``COALESCE(rated_at, first_seen)``.
  ``rated_at`` is the real rating instant; ``first_seen`` is ingestion time.
- ``repost_builder_migration`` rows carry ``COALESCE(first_seen, created_at)``,
  which is when the track was ingested, i.e. *before* it was even placed in
  a builder playlist, let alone decided.

Trusting those ingestion stamps would order decisions before the sync run
that surfaced them and leak future reposts into the training window, so the
loader treats them as unknown and lets :func:`resolve_decision_time` derive
a proxy from ``playlist_batch`` and the sync log, exactly as it did before
the ledger existed.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Sequence

from web.backend.soundcloud_metadata import parse_soundcloud_datetime

LABEL_BY_DECISION: dict[str, int] = {"keep": 1, "nope": 0}
MIGRATION_SURFACE_SUFFIX = "_migration"
UPLOAD_MIGRATION_SURFACE = "upload_feed_migration"


@dataclass(frozen=True)
class ReposterEvent:
    artist_id: int
    ranking: int | None
    is_following: bool
    event_at: datetime | None
    seen_at: datetime | None
    exact_time: bool = False


@dataclass(frozen=True)
class TrackDecision:
    soundcloud_id: str
    label: int
    event_type: str
    uploader_id: int | None
    uploader_ranking: int | None
    uploader_is_following: bool
    uploader_source: str
    duration_ms: int | None
    title: str
    genre: str | None
    released_at: datetime | None
    first_seen: datetime | None
    playlist_batch: int | None
    reposters: tuple[ReposterEvent, ...]
    decided_at: datetime | None = None
    decided_at_source: str = "unknown"


def _normalized_name_sql(column: str) -> str:
    return (
        f"LOWER(TRIM(REPLACE(REPLACE(REPLACE(COALESCE({column}, ''), "
        "'.', ''), '!', ''), '?', '')))"
    )


_CURRENT_LABEL_SQL = """
SELECT soundcloud_id, decision, decided_at, surface
FROM sc_track_decisions
WHERE is_current = 1 AND decision IN ('keep', 'nope')
"""


def _load_reposters(
    conn: sqlite3.Connection,
) -> dict[int, tuple[ReposterEvent, ...]]:
    rows = conn.execute(
        f"""
        SELECT dtr.discovery_track_id, dtr.discovery_artist_id, da.ranking,
               da.is_following,
               COALESCE(dtr.reposted_at, dtr.raw_reposted_at) AS event_at,
               dtr.seen_at, dtr.repost_time_precision
        FROM discovery_track_reposters dtr
        JOIN discovery_tracks dt ON dt.id = dtr.discovery_track_id
        JOIN discovery_artists da ON da.id = dtr.discovery_artist_id
        WHERE dt.soundcloud_id IN (SELECT soundcloud_id FROM ({_CURRENT_LABEL_SQL}))
        ORDER BY dtr.discovery_track_id, da.ranking IS NULL, da.ranking,
                 dtr.discovery_artist_id
        """
    ).fetchall()
    grouped: dict[int, list[ReposterEvent]] = {}
    for row in rows:
        grouped.setdefault(row["discovery_track_id"], []).append(
            ReposterEvent(
                artist_id=row["discovery_artist_id"],
                ranking=row["ranking"],
                is_following=bool(row["is_following"]),
                event_at=parse_soundcloud_datetime(row["event_at"]),
                seen_at=parse_soundcloud_datetime(row["seen_at"]),
                exact_time=row["repost_time_precision"] == "exact",
            )
        )
    return {track_id: tuple(events) for track_id, events in grouped.items()}


# One row per current keep/nope decision. A track may exist in either or both
# of discovery_tracks (repost builder) and sc_artist_uploads (upload feed), so
# every metadata column is coalesced across the two.
_DECISIONS_SQL = f"""
SELECT d.soundcloud_id, d.decision, d.decided_at, d.surface,
       dt.id AS track_id, dt.playlist_batch,
       COALESCE(dt.title, u.title) AS title,
       COALESCE(dt.duration_ms, u.duration_ms) AS duration_ms,
       COALESCE(dt.genre, u.genre) AS genre,
       COALESCE(dt.released_at, u.released_at, u.uploaded_at) AS released_at,
       COALESCE(dt.first_seen, u.first_seen) AS first_seen,
       u.id AS upload_id, u.rated_at,
       by_id.id AS uploader_by_id, by_id.ranking AS uploader_by_id_rank,
       by_id.is_following AS uploader_by_id_following,
       by_upload.id AS uploader_by_upload,
       by_upload.ranking AS uploader_by_upload_rank,
       by_upload.is_following AS uploader_by_upload_following,
       by_name.id AS uploader_by_name, by_name.ranking AS uploader_by_name_rank,
       by_name.is_following AS uploader_by_name_following
FROM ({_CURRENT_LABEL_SQL}) d
LEFT JOIN discovery_tracks dt ON dt.soundcloud_id = d.soundcloud_id
LEFT JOIN sc_artist_uploads u ON u.soundcloud_id = d.soundcloud_id
LEFT JOIN discovery_artists by_id
  ON by_id.soundcloud_user_id = dt.uploader_soundcloud_id
LEFT JOIN discovery_artists by_upload ON by_upload.id = u.discovery_artist_id
LEFT JOIN discovery_artists by_name
  ON by_name.display_name_normalized = {_normalized_name_sql("dt.artist_name")}
 AND dt.artist_name IS NOT NULL AND dt.artist_name != ''
WHERE dt.id IS NOT NULL OR u.id IS NOT NULL
ORDER BY d.soundcloud_id
"""


def _resolve_uploader(row: sqlite3.Row) -> tuple[int | None, int | None, bool, str]:
    """Pick the uploader by the most reliable available link."""
    for source in ("by_id", "by_upload", "by_name"):
        artist_id = row[f"uploader_{source}"]
        if artist_id is not None:
            return (
                artist_id,
                row[f"uploader_{source}_rank"],
                bool(row[f"uploader_{source}_following"]),
                {"by_id": "soundcloud_id", "by_upload": "upload_event"}.get(
                    source, "name_match"
                ),
            )
    return None, None, False, "none"


def _event_type(row: sqlite3.Row, reposters: tuple[ReposterEvent, ...]) -> str:
    has_release = row["upload_id"] is not None
    if has_release and reposters:
        return "both"
    if has_release:
        return "release"
    return "repost"


def _decision_time(row: sqlite3.Row) -> tuple[datetime | None, str]:
    """Trust the ledger stamp unless the v62 migration synthesised it.

    Live surfaces stamp the decision instant. Migrated upload rows are only
    real when the legacy ``rated_at`` existed (the migration coalesced it
    with ingestion time); migrated builder rows are always ingestion time,
    so they fall through to the sync-log proxy in ``resolve_decision_time``.
    """
    surface = row["surface"] or ""
    if not surface.endswith(MIGRATION_SURFACE_SUFFIX):
        return parse_soundcloud_datetime(row["decided_at"]), "ledger"
    if surface == UPLOAD_MIGRATION_SURFACE and row["rated_at"]:
        return parse_soundcloud_datetime(row["rated_at"]), "upload_rated_at"
    return None, "unknown"


def _track_decision(
    row: sqlite3.Row, reposters: tuple[ReposterEvent, ...]
) -> TrackDecision:
    uploader_id, uploader_rank, following, source = _resolve_uploader(row)
    decided_at, decided_at_source = _decision_time(row)
    return TrackDecision(
        soundcloud_id=str(row["soundcloud_id"]),
        label=LABEL_BY_DECISION[row["decision"]],
        event_type=_event_type(row, reposters),
        uploader_id=uploader_id,
        uploader_ranking=uploader_rank,
        uploader_is_following=following,
        uploader_source=source,
        duration_ms=row["duration_ms"] or None,
        title=row["title"] or "",
        genre=row["genre"],
        released_at=parse_soundcloud_datetime(row["released_at"]),
        first_seen=parse_soundcloud_datetime(row["first_seen"]),
        playlist_batch=row["playlist_batch"],
        reposters=reposters,
        decided_at=decided_at,
        decided_at_source=decided_at_source,
    )


def load_track_decisions(conn: sqlite3.Connection) -> list[TrackDecision]:
    """Return exactly one keep/nope decision per SoundCloud track.

    Reads the current row of the ``sc_track_decisions`` ledger; the unique
    partial index on ``is_current = 1`` guarantees one label per track.
    Ledger rows whose track is unknown to both discovery tables are skipped.
    """
    reposters = _load_reposters(conn)
    return [
        _track_decision(row, reposters.get(row["track_id"], ()))
        for row in conn.execute(_DECISIONS_SQL).fetchall()
    ]


def load_sync_run_starts(conn: sqlite3.Connection) -> list[datetime]:
    """Start times of every sync run that created a playlist batch, in order.

    ``mark_tracks_in_playlist`` runs on every sync with selections (dry runs
    included), so the k-th such run created ``playlist_batch = k``.
    """
    rows = conn.execute(
        """
        SELECT started_at FROM discovery_sync_log
        WHERE tracks_added > 0 OR mixes_added > 0
        ORDER BY started_at, id
        """
    ).fetchall()
    starts = [parse_soundcloud_datetime(row["started_at"]) for row in rows]
    return [value for value in starts if value is not None]


def _next_run_after(runs: Sequence[datetime], moment: datetime) -> datetime | None:
    for start in runs:
        if start > moment:
            return start
    return None


def resolve_decision_time(
    decision: TrackDecision, runs: Sequence[datetime], now: datetime
) -> TrackDecision:
    """Attach the best available decision time proxy.

    Bucket decisions are committed by the next sync run, so a track placed in
    batch ``k`` was decided no later than the start of the run that created
    batch ``k + 1``. Resolution is therefore one sync cycle, which is enough
    for chronological ordering but not for intra-batch ordering.
    """
    if decision.decided_at is not None:
        return decision
    batch = decision.playlist_batch
    if batch is not None and batch < len(runs):
        return replace(
            decision, decided_at=runs[batch], decided_at_source="next_sync_after_batch"
        )
    if batch is not None:
        return replace(decision, decided_at=now, decided_at_source="open_batch_now")
    if decision.first_seen is not None:
        following = _next_run_after(runs, decision.first_seen)
        if following is not None:
            return replace(
                decision,
                decided_at=following,
                decided_at_source="next_sync_after_first_seen",
            )
        return replace(
            decision, decided_at=decision.first_seen, decided_at_source="first_seen"
        )
    return replace(decision, decided_at=now, decided_at_source="unknown_now")


def timeline_track_decisions(
    conn: sqlite3.Connection, now: datetime | None = None
) -> list[TrackDecision]:
    """Decisions with resolved times, oldest first (ties by SoundCloud ID)."""
    current = now or datetime.now(timezone.utc)
    runs = load_sync_run_starts(conn)
    resolved = [
        resolve_decision_time(decision, runs, current)
        for decision in load_track_decisions(conn)
    ]
    return sorted(resolved, key=lambda item: (item.decided_at, item.soundcloud_id))
