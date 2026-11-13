"""DB reads and writes behind GET /api/follow-suggestions.

Scoring itself is pure (web/backend/follow_suggestions.py); this module only
turns tables into its inputs and records dismissals / label overrides.
"""

import sqlite3
from datetime import UTC, datetime
from typing import Any

from music_minion.domain.library.providers.soundcloud.like_uploaders import (
    permalink_from_url,
)
from web.backend.follow_suggestions import (
    Account,
    Activity,
    Context,
    EvidenceTrack,
    Resolution,
    account_decisions,
    account_keys,
    activity_resolutions,
    combine_resolutions,
    name_key,
    rank_entities,
    uploader_resolutions,
)

# One tracks row per soundcloud_id: local files carry the cleanest credits.
# Probes by source so the (source, soundcloud_id) index applies.
_TRACK_FOR = """COALESCE(
    (SELECT id FROM tracks WHERE source IN ('local', 'file')
        AND soundcloud_id = {col} ORDER BY id LIMIT 1),
    (SELECT id FROM tracks WHERE source = 'soundcloud' AND soundcloud_id = {col}))"""

_LIKED_SQL = f"""
    SELECT l.soundcloud_id, l.liked_at, l.like_order,
           COALESCE(t.title, dt.title, u.title, '') AS title,
           COALESCE(t.artist, dt.artist_name, '') AS artist,
           t.remix_artist,
           COALESCE(l.uploader_soundcloud_id, dt.uploader_soundcloud_id,
                    u.uploader_soundcloud_id) AS uploader_id,
           COALESCE(l.uploader_permalink, da.slug) AS uploader_permalink,
           COALESCE(l.uploader_username, da.display_name) AS uploader_username,
           COALESCE(dt.permalink_url, u.permalink_url) AS track_url
    FROM sc_likes l
    LEFT JOIN tracks t ON t.id = {_TRACK_FOR.format(col="l.soundcloud_id")}
    LEFT JOIN discovery_tracks dt ON dt.soundcloud_id = l.soundcloud_id
    LEFT JOIN sc_artist_uploads u ON u.soundcloud_id = l.soundcloud_id
    LEFT JOIN discovery_artists da ON da.id = (
        SELECT id FROM discovery_artists WHERE soundcloud_user_id =
            COALESCE(dt.uploader_soundcloud_id, u.uploader_soundcloud_id)
        LIMIT 1)
"""

_KEPT_SQL = f"""
    SELECT d.soundcloud_id, d.decided_at AS liked_at, NULL AS like_order,
           COALESCE(t.title, dt.title, u.title, '') AS title,
           COALESCE(t.artist, dt.artist_name, '') AS artist,
           t.remix_artist,
           COALESCE(dt.uploader_soundcloud_id, u.uploader_soundcloud_id) AS uploader_id,
           da.slug AS uploader_permalink, da.display_name AS uploader_username,
           COALESCE(dt.permalink_url, u.permalink_url) AS track_url
    FROM sc_track_decisions d
    LEFT JOIN tracks t ON t.id = {_TRACK_FOR.format(col="d.soundcloud_id")}
    LEFT JOIN discovery_tracks dt ON dt.soundcloud_id = d.soundcloud_id
    LEFT JOIN sc_artist_uploads u ON u.soundcloud_id = d.soundcloud_id
    LEFT JOIN discovery_artists da ON da.id = (
        SELECT id FROM discovery_artists WHERE soundcloud_user_id =
            COALESCE(dt.uploader_soundcloud_id, u.uploader_soundcloud_id)
        LIMIT 1)
    WHERE d.is_current = 1 AND d.decision = 'keep'
      AND NOT EXISTS (SELECT 1 FROM sc_likes l WHERE l.soundcloud_id = d.soundcloud_id)
"""


def _credit(value: str | None) -> str:
    """'A; B' credits split like 'A, B'."""
    return (value or "").replace(";", ",")


def _evidence_track(row: sqlite3.Row, liked: bool) -> EvidenceTrack:
    uploader_id = str(row["uploader_id"]) if row["uploader_id"] else None
    return EvidenceTrack(
        soundcloud_id=str(row["soundcloud_id"]),
        title=_credit(row["title"]),
        artist=_credit(row["artist"]),
        remix_artist=_credit(row["remix_artist"]) or None,
        liked=liked,
        liked_at=row["liked_at"],
        uploader_id=uploader_id,
        uploader_permalink=row["uploader_permalink"]
        or (permalink_from_url(row["track_url"]) if uploader_id else None),
        uploader_username=row["uploader_username"],
        like_order=row["like_order"],
    )


def load_evidence_tracks(conn: sqlite3.Connection) -> list[EvidenceTrack]:
    """Every liked track plus current keeps that were never liked."""
    liked = [_evidence_track(r, True) for r in conn.execute(_LIKED_SQL)]
    kept = [_evidence_track(r, False) for r in conn.execute(_KEPT_SQL)]
    return liked + kept


def load_followed(conn: sqlite3.Connection) -> tuple[Account, ...]:
    rows = conn.execute(
        """SELECT soundcloud_user_id, display_name, slug FROM discovery_artists
        WHERE is_following = 1"""
    ).fetchall()
    return tuple(
        Account(str(r[0]) if r[0] else "", r["display_name"], r["slug"]) for r in rows
    )


def load_resolutions(conn: sqlite3.Connection) -> dict[str, Resolution]:
    """Cached name -> account resolutions (misses included, id None)."""
    rows = conn.execute(
        """SELECT name_key, soundcloud_user_id, permalink, display_name,
                  confidence, source FROM sc_name_resolutions"""
    ).fetchall()
    return {
        r["name_key"]: Resolution(
            str(r["soundcloud_user_id"]) if r["soundcloud_user_id"] else None,
            r["permalink"],
            r["display_name"],
            r["confidence"] or "none",
            r["source"] or "",
        )
        for r in rows
    }


def load_activity(conn: sqlite3.Connection) -> dict[str, Activity]:
    rows = conn.execute("SELECT * FROM sc_account_activity").fetchall()
    return {
        str(r["soundcloud_user_id"]): Activity(
            r["username"],
            r["permalink"],
            r["avatar_url"],
            r["followers"],
            r["last_upload_at"],
            r["last_repost_at"],
            r["uploads_90d"] or 0,
            r["reposts_90d"] or 0,
            bool(r["is_label"]),
        )
        for r in rows
    }


def load_dismissed(conn: sqlite3.Connection) -> frozenset[str]:
    rows = conn.execute("SELECT soundcloud_user_id FROM follow_suggestion_dismissals")
    return frozenset(str(r[0]) for r in rows)


def load_label_overrides(conn: sqlite3.Connection) -> dict[str, bool]:
    rows = conn.execute(
        "SELECT soundcloud_user_id, is_label FROM follow_suggestion_label_overrides"
    )
    return {str(r[0]): bool(r[1]) for r in rows}


def discovery_resolutions(conn: sqlite3.Connection) -> dict[str, Resolution]:
    """Name key -> discovery_artists account, by display/slug keys and the
    artist match view (merge overrides). Source (b) of name resolution."""
    rows = conn.execute(
        """SELECT soundcloud_user_id, slug, display_name, NULL AS local_name
        FROM discovery_artists WHERE soundcloud_user_id IS NOT NULL
        UNION ALL
        SELECT da.soundcloud_user_id, da.slug, da.display_name, amr.local_name
        FROM artist_match_resolved amr
        JOIN discovery_artists da ON da.id = amr.discovery_artist_id
        WHERE da.soundcloud_user_id IS NOT NULL"""
    ).fetchall()
    found: dict[str, Resolution] = {}
    for r in rows:
        keys = (
            {name_key(r["local_name"])}
            if r["local_name"]
            else account_keys(r["display_name"], r["slug"])
        )
        resolution = Resolution(
            str(r["soundcloud_user_id"]), r["slug"], r["display_name"], "high",
            "discovery_artists",
        )  # fmt: skip
        found.update({k: resolution for k in keys - {""} if k not in found})
    return found


def load_context(conn: sqlite3.Connection, now: datetime | None = None) -> Context:
    return Context(
        followed=load_followed(conn),
        resolutions=load_resolutions(conn),
        activity=load_activity(conn),
        dismissed=load_dismissed(conn),
        label_overrides=load_label_overrides(conn),
        now=now or datetime.now(UTC),
    )


def dismiss(conn: sqlite3.Connection, key: str) -> None:
    """Permanent: a dismissed account or name never comes back."""
    conn.execute(
        """INSERT INTO follow_suggestion_dismissals (soundcloud_user_id)
        VALUES (?) ON CONFLICT(soundcloud_user_id) DO NOTHING""",
        (key,),
    )
    conn.commit()


def set_label_override(conn: sqlite3.Connection, key: str, is_label: bool) -> None:
    conn.execute(
        """INSERT INTO follow_suggestion_label_overrides (soundcloud_user_id, is_label)
        VALUES (?, ?) ON CONFLICT(soundcloud_user_id) DO UPDATE SET
            is_label = excluded.is_label, updated_at = CURRENT_TIMESTAMP""",
        (key, int(is_label)),
    )
    conn.commit()


def resolved_context(
    conn: sqlite3.Connection, tracks: list[EvidenceTrack], now: datetime | None = None
) -> Context:
    """load_context with live sources (a) uploaders and (b) discovery_artists
    layered over the cached resolutions (which hold the API search results).

    Dismissals and label overrides on 'name:<k>' also apply to every account
    k resolves to, in the cache or live, whether or not k is still credited."""
    ctx = load_context(conn, now)
    resolutions = combine_resolutions(
        uploader_resolutions(tracks),
        activity_resolutions(ctx.activity),
        discovery_resolutions(conn),
        ctx.resolutions,
    )
    aliases = [
        (k, r.soundcloud_user_id)
        for source in (ctx.resolutions, resolutions)  # the full cache, then live
        for k, r in source.items()
    ]
    dismissed, overrides = account_decisions(
        ctx.dismissed, ctx.label_overrides, aliases
    )
    return ctx._replace(
        resolutions=resolutions, dismissed=dismissed, label_overrides=overrides
    )


def compute_ranked(
    conn: sqlite3.Connection, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Every suggestion (artists and labels together), best score first."""
    tracks = load_evidence_tracks(conn)
    return rank_entities(tracks, resolved_context(conn, tracks, now))
