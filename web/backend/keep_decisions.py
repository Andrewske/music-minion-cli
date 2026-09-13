"""One track-level keep/nope decision per SoundCloud track.

This is the single place that turns the legacy status columns
(``discovery_tracks.status`` and ``sc_artist_uploads.status``) into decision
records. Both the artist-quality aggregation (#60) and the offline keep-model
dataset (#61) read from here, so when a dedicated decision ledger lands only
:func:`load_track_decisions` has to change.

Labels: ``liked`` is a keep, ``dismissed`` is a nope. ``in_playlist``,
``unseen``, ``visible`` and ``hidden`` are workflow states, never labels.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Sequence

from web.backend.soundcloud_metadata import parse_soundcloud_datetime

KEEP_STATUSES: frozenset[str] = frozenset({"liked"})
NOPE_STATUSES: frozenset[str] = frozenset({"dismissed"})


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


def _label(status: str) -> int | None:
    if status in KEEP_STATUSES:
        return 1
    if status in NOPE_STATUSES:
        return 0
    return None


def _normalized_name_sql(column: str) -> str:
    return (
        f"LOWER(TRIM(REPLACE(REPLACE(REPLACE(COALESCE({column}, ''), "
        "'.', ''), '!', ''), '?', '')))"
    )


def _load_reposters(
    conn: sqlite3.Connection,
) -> dict[int, tuple[ReposterEvent, ...]]:
    rows = conn.execute(
        """
        SELECT dtr.discovery_track_id, dtr.discovery_artist_id, da.ranking,
               da.is_following,
               COALESCE(dtr.reposted_at, dtr.raw_reposted_at) AS event_at,
               dtr.seen_at, dtr.repost_time_precision
        FROM discovery_track_reposters dtr
        JOIN discovery_tracks dt ON dt.id = dtr.discovery_track_id
        JOIN discovery_artists da ON da.id = dtr.discovery_artist_id
        WHERE dt.status IN ('liked', 'dismissed')
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


_DISCOVERY_DECISIONS_SQL = f"""
SELECT dt.id, dt.soundcloud_id, dt.status, dt.title, dt.duration_ms, dt.genre,
       dt.released_at, dt.first_seen, dt.playlist_batch,
       by_id.id AS uploader_by_id, by_id.ranking AS uploader_by_id_rank,
       by_id.is_following AS uploader_by_id_following,
       by_upload.id AS uploader_by_upload,
       by_upload.ranking AS uploader_by_upload_rank,
       by_upload.is_following AS uploader_by_upload_following,
       by_name.id AS uploader_by_name, by_name.ranking AS uploader_by_name_rank,
       by_name.is_following AS uploader_by_name_following
FROM discovery_tracks dt
LEFT JOIN discovery_artists by_id
  ON by_id.soundcloud_user_id = dt.uploader_soundcloud_id
LEFT JOIN sc_artist_uploads u ON u.soundcloud_id = dt.soundcloud_id
LEFT JOIN discovery_artists by_upload ON by_upload.id = u.discovery_artist_id
LEFT JOIN discovery_artists by_name
  ON by_name.display_name_normalized = {_normalized_name_sql("dt.artist_name")}
 AND dt.artist_name IS NOT NULL AND dt.artist_name != ''
WHERE dt.status IN ('liked', 'dismissed')
ORDER BY dt.id
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


def _discovery_decision(
    row: sqlite3.Row, reposters: tuple[ReposterEvent, ...]
) -> TrackDecision:
    uploader_id, uploader_rank, following, source = _resolve_uploader(row)
    has_release = row["uploader_by_upload"] is not None
    if has_release and reposters:
        event_type = "both"
    elif has_release:
        event_type = "release"
    else:
        event_type = "repost"
    return TrackDecision(
        soundcloud_id=str(row["soundcloud_id"]),
        label=_label(row["status"]) or 0,
        event_type=event_type,
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
    )


def _load_discovery_decisions(conn: sqlite3.Connection) -> list[TrackDecision]:
    reposters = _load_reposters(conn)
    seen: set[str] = set()
    output: list[TrackDecision] = []
    for row in conn.execute(_DISCOVERY_DECISIONS_SQL).fetchall():
        sc_id = str(row["soundcloud_id"])
        if sc_id in seen or _label(row["status"]) is None:
            continue
        seen.add(sc_id)
        output.append(_discovery_decision(row, reposters.get(row["id"], ())))
    return output


def _load_upload_decisions(conn: sqlite3.Connection) -> list[TrackDecision]:
    rows = conn.execute(
        """
        SELECT u.soundcloud_id, u.status, u.title, u.duration_ms, u.genre,
               COALESCE(u.released_at, u.uploaded_at) AS released_at,
               u.first_seen, u.rated_at,
               da.id AS artist_id, da.ranking, da.is_following
        FROM sc_artist_uploads u
        JOIN discovery_artists da ON da.id = u.discovery_artist_id
        WHERE u.status IN ('liked', 'dismissed')
        ORDER BY u.id
        """
    ).fetchall()
    output: list[TrackDecision] = []
    for row in rows:
        rated_at = parse_soundcloud_datetime(row["rated_at"])
        output.append(
            TrackDecision(
                soundcloud_id=str(row["soundcloud_id"]),
                label=_label(row["status"]) or 0,
                event_type="release",
                uploader_id=row["artist_id"],
                uploader_ranking=row["ranking"],
                uploader_is_following=bool(row["is_following"]),
                uploader_source="upload_event",
                duration_ms=row["duration_ms"] or None,
                title=row["title"] or "",
                genre=row["genre"],
                released_at=parse_soundcloud_datetime(row["released_at"]),
                first_seen=parse_soundcloud_datetime(row["first_seen"]),
                playlist_batch=None,
                reposters=(),
                decided_at=rated_at,
                decided_at_source="upload_rated_at" if rated_at else "unknown",
            )
        )
    return output


def load_track_decisions(conn: sqlite3.Connection) -> list[TrackDecision]:
    """Return exactly one keep/nope decision per SoundCloud track.

    A track rated through the uploads feed and also decided in the discovery
    playlist keeps the upload decision (it carries an explicit ``rated_at``).
    """
    uploads = _load_upload_decisions(conn)
    upload_ids = {decision.soundcloud_id for decision in uploads}
    discovery = [
        decision
        for decision in _load_discovery_decisions(conn)
        if decision.soundcloud_id not in upload_ids
    ]
    return sorted(uploads + discovery, key=lambda item: item.soundcloud_id)


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
