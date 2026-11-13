"""Nightly fill of the follow-suggestion caches (runs from sc_feed_worker).

1. Kevin's own account goes into the dismissals, so it is never suggested.
2. Credited names resolve to SC accounts: local sources (liked-track
   uploaders, discovery_artists) are stored as-is; names with 3+ credits that
   are still unresolved go to SoundCloud user search, up to 100 per run.
   Misses are cached too and retried after 30 days.
3. Activity (followers, avatar, recent uploads/reposts, label heuristic) is
   refreshed for up to 150 candidate accounts per run, each at most weekly.

Errors: a request that failed never writes. An error about one account
(404, other 4xx, bad JSON, a malformed payload or a profile for some other
account) skips that account or name and keeps its old row; anything else
(5xx, 429, auth, network) means SoundCloud itself is unwell and stops the
run (see sc_errors).
"""

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any, NamedTuple

from loguru import logger

from music_minion.core.database import get_db_connection
from music_minion.domain.library.providers.soundcloud.api import (
    get_user_reposts,
    get_user_tracks,
)
from music_minion.domain.library.providers.soundcloud.user_lookup import (
    get_me,
    get_user,
    search_users,
)
from web.backend.follow_suggestions import (
    Context,
    EvidenceTrack,
    Resolution,
    collect_hits,
    credits_others,
    name_key,
    parse_time,
    rank_entities,
)
from web.backend.queries.follow_suggestions import (
    load_evidence_tracks,
    resolved_context,
)
from web.backend.sc_errors import is_service_error
from web.backend.soundcloud_metadata import raw_repost_timestamp

NAME_SEARCH_LIMIT = 100
ACTIVITY_LIMIT = 150
# Only the best-evidence accounts get activity: the page shows 200 artists +
# 100 labels, and the factors only lower a score, so deeper ones never surface.
ACTIVITY_POOL = 400
MIN_CREDITS_FOR_SEARCH = 3
MISS_RETRY_DAYS = 30
ACTIVITY_MAX_AGE_DAYS = 7
ACTIVITY_WINDOW_DAYS = 90
ACTIVITY_PAGE = 50


class CacheRunStats(NamedTuple):
    names_searched: int
    names_resolved: int
    activity_refreshed: int
    stopped: str | None = None  # the service-wide error that ended the run


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def pick_search_match(users: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    """The most-followed user whose username or permalink key equals `key`."""
    exact = [
        u
        for u in users
        if u.get("id")
        and key in (name_key(u.get("username")), name_key(u.get("permalink")))
    ]
    return max(exact, key=lambda u: u.get("followers_count") or 0, default=None)


def _track_count(suggestion: dict[str, Any]) -> int:
    return sum(suggestion["evidence"].values())


def names_to_search(
    ranked: list[dict[str, Any]], fresh_misses: set[str], limit: int
) -> list[tuple[str, str]]:
    """(name_key, display) for unresolved names with 3+ credits, best first."""
    names = [
        (s["key"][5:], s["display_name"])
        for s in sorted(ranked, key=lambda s: -s["evidence_score"])
        if s["key"].startswith("name:")
        and _track_count(s) >= MIN_CREDITS_FOR_SEARCH
        and s["key"][5:] not in fresh_misses
    ]
    return names[:limit]


def accounts_to_refresh(
    ranked: list[dict[str, Any]], fetched_at: dict[str, str], now: datetime, limit: int
) -> list[str]:
    """The top ACTIVITY_POOL accounts by evidence whose activity is missing or
    over a week old, best first."""
    cutoff = now - timedelta(days=ACTIVITY_MAX_AGE_DAYS)
    accounts = [
        s for s in sorted(ranked, key=lambda s: -s["evidence_score"])
        if s["soundcloud_user_id"]
    ][:ACTIVITY_POOL]  # fmt: skip
    stale = [
        s["key"]
        for s in accounts
        if (parse_time(fetched_at.get(s["key"])) or datetime.min.replace(tzinfo=UTC))
        < cutoff
    ]
    return stale[:limit]


def looks_like_label(username: str | None, uploads: list[dict[str, Any]]) -> bool:
    """Most recent uploads explicitly credit someone other than the account.

    An upload with no metadata_artist and no 'X - Title' credit is unknown."""
    credits = [(t.get("metadata_artist"), t.get("title") or "") for t in uploads]
    return credits_others({name_key(username)}, credits)


def _latest(times: list[datetime | None]) -> datetime | None:
    return max((t for t in times if t), default=None)


def summarize_activity(
    user: dict[str, Any] | None,
    uploads: list[dict[str, Any]],
    reposts: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    """One sc_account_activity row from a profile and one page of each feed.

    Repost payloads rarely carry a repost time, so a repost is dated by its
    explicit timestamp when present, else by the track's upload time (a lower
    bound: a repost can't predate the upload).
    """
    user = user or next((t.get("user") for t in uploads if t.get("user")), None) or {}
    upload_times = [parse_time(t.get("created_at")) for t in uploads]
    repost_times = [
        parse_time(raw_repost_timestamp(t) or t.get("created_at")) for t in reposts
    ]
    since = now - timedelta(days=ACTIVITY_WINDOW_DAYS)
    last_upload, last_repost = _latest(upload_times), _latest(repost_times)
    return {
        "permalink": user.get("permalink"),
        "username": user.get("username"),
        "avatar_url": user.get("avatar_url"),
        "followers": user.get("followers_count"),
        "last_upload_at": last_upload.isoformat() if last_upload else None,
        "last_repost_at": last_repost.isoformat() if last_repost else None,
        "uploads_90d": sum(1 for t in upload_times if t and t >= since),
        "reposts_90d": sum(1 for t in repost_times if t and t >= since),
        "is_label": int(looks_like_label(user.get("username"), uploads)),
    }


# ---------------------------------------------------------------------------
# DB writes
# ---------------------------------------------------------------------------


def _store_resolutions(conn: sqlite3.Connection, rows: dict[str, Resolution]) -> None:
    conn.executemany(
        """INSERT INTO sc_name_resolutions
            (name_key, soundcloud_user_id, permalink, display_name, confidence, source)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(name_key) DO UPDATE SET
            soundcloud_user_id = excluded.soundcloud_user_id,
            permalink = excluded.permalink, display_name = excluded.display_name,
            confidence = excluded.confidence, source = excluded.source,
            resolved_at = CURRENT_TIMESTAMP
        WHERE sc_name_resolutions.source != 'manual'""",
        [(k, *r) for k, r in sorted(rows.items())],
    )
    conn.commit()


def _store_activity(
    conn: sqlite3.Connection, user_id: str, row: dict[str, Any]
) -> None:
    columns = ", ".join(row)
    updates = ", ".join(f"{c} = excluded.{c}" for c in row)
    conn.execute(
        f"""INSERT INTO sc_account_activity (soundcloud_user_id, {columns})
        VALUES (?, {", ".join("?" * len(row))})
        ON CONFLICT(soundcloud_user_id) DO UPDATE SET {updates},
            fetched_at = CURRENT_TIMESTAMP""",
        (user_id, *row.values()),
    )
    conn.commit()


def _fresh_misses(conn: sqlite3.Connection, now: datetime) -> set[str]:
    cutoff = (now - timedelta(days=MISS_RETRY_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        """SELECT name_key FROM sc_name_resolutions
        WHERE soundcloud_user_id IS NULL AND resolved_at >= ?""",
        (cutoff,),
    )
    return {r[0] for r in rows}


def _activity_fetched_at(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute(
        "SELECT soundcloud_user_id, fetched_at FROM sc_account_activity"
    )
    return {str(r[0]): r[1] for r in rows}


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def _ranked_now(
    conn: sqlite3.Connection, tracks: list[EvidenceTrack], now: datetime
) -> list[dict[str, Any]]:
    return rank_entities(tracks, resolved_context(conn, tracks, now))


def dismiss_own_account(state: Any) -> tuple[Any, str | None]:
    """Kevin's own SC account is a permanent dismissal (never suggested).

    Returns (state, service error that should stop the run, or None)."""
    state, me, error = get_me(state)
    if error or not me or not me.get("id"):
        logger.warning(
            f"follow caches: /me lookup failed ({error}); own account not excluded"
        )
        return state, error if error and is_service_error(error) else None
    with get_db_connection() as conn:
        conn.execute(
            """INSERT INTO follow_suggestion_dismissals (soundcloud_user_id)
            VALUES (?) ON CONFLICT(soundcloud_user_id) DO NOTHING""",
            (str(me["id"]),),
        )
        conn.commit()
    return state, None


def store_local_resolutions(
    conn: sqlite3.Connection, tracks: list[EvidenceTrack], ctx: Context
) -> None:
    """Cache local resolutions for every credited name that has one."""
    credited = {h.ref[5:] for h in collect_hits(tracks) if h.ref.startswith("name:")}
    local = {
        k: r
        for k, r in ctx.resolutions.items()
        if r.source in ("uploader", "discovery_artists", "activity") and k in credited
    }
    _store_resolutions(conn, local)


def _search_resolution(users: list[dict[str, Any]], key: str) -> Resolution:
    match = pick_search_match(users, key)
    if not match:
        return Resolution(None, None, None, "none", "search")
    return Resolution(
        str(match["id"]),
        match.get("permalink"),
        match.get("username"),
        "medium",
        "search",
    )


def search_names(
    state: Any, names: list[tuple[str, str]]
) -> tuple[Any, dict[str, Resolution], str | None]:
    """SoundCloud user search per name: (state, hits and misses, stop error).

    A failed search records nothing (not even a miss); a service-wide error
    ends the loop."""
    found: dict[str, Resolution] = {}
    for key, display in names:
        state, users, error = search_users(state, display)
        if error and is_service_error(error):
            logger.warning(
                f"follow caches: name search stopped at {display!r}: {error}"
            )
            return state, found, error
        if error:
            logger.warning(f"follow caches: search for {display!r} failed: {error}")
            continue
        found[key] = _search_resolution(users, key)
    return state, found, None


def fetch_activity(
    state: Any, user_id: str, now: datetime
) -> tuple[Any, dict[str, Any] | None, str | None]:
    """(state, sc_account_activity row, error) from one profile and one page of
    uploads and reposts. Any failed request means no row."""
    state, user, error = get_user(state, user_id)
    if error:
        return state, None, error
    if not user or str(user.get("id")) != user_id:
        return state, None, f"Malformed response: profile is not {user_id}"
    state, uploads, error = get_user_tracks(
        state, user_id, limit=ACTIVITY_PAGE, max_pages=1
    )
    if error:
        return state, None, error
    state, reposts, error = get_user_reposts(
        state, user_id, limit=ACTIVITY_PAGE, max_pages=1
    )
    if error:
        return state, None, error
    return state, summarize_activity(user, uploads, reposts, now), None


def refresh_activity(
    state: Any, conn: sqlite3.Connection, user_ids: list[str], now: datetime
) -> tuple[Any, int, str | None]:
    """Refresh each account's activity row: (state, rows written, stop error).

    An account whose fetch failed keeps its old row and is retried next run."""
    done = 0
    for user_id in user_ids:
        state, row, error = fetch_activity(state, user_id, now)
        if error and is_service_error(error):
            logger.warning(f"follow caches: activity stopped at {user_id}: {error}")
            return state, done, error
        if error or row is None:
            logger.warning(f"follow caches: activity skipped {user_id}: {error}")
            continue
        _store_activity(conn, user_id, row)
        done += 1
    return state, done, None


def _search_stats(searched: dict[str, Resolution]) -> tuple[int, int]:
    return len(searched), sum(1 for r in searched.values() if r.soundcloud_user_id)


def _fill_caches(state: Any, conn: sqlite3.Connection, now: datetime) -> CacheRunStats:
    tracks = load_evidence_tracks(conn)
    store_local_resolutions(conn, tracks, resolved_context(conn, tracks, now))
    ranked = _ranked_now(conn, tracks, now)
    names = names_to_search(ranked, _fresh_misses(conn, now), NAME_SEARCH_LIMIT)
    state, searched, stopped = search_names(state, names)
    _store_resolutions(conn, searched)
    if stopped:
        return CacheRunStats(*_search_stats(searched), 0, stopped)
    ranked = _ranked_now(conn, tracks, now)
    due = accounts_to_refresh(ranked, _activity_fetched_at(conn), now, ACTIVITY_LIMIT)
    state, refreshed, stopped = refresh_activity(state, conn, due, now)
    return CacheRunStats(*_search_stats(searched), refreshed, stopped)


def refresh_follow_suggestion_caches(state: Any) -> CacheRunStats:
    """The nightly job: own account, name resolution, activity. Stops at the
    first service-wide error. May raise; the feed worker wraps it."""
    now = datetime.now(UTC)
    state, stopped = dismiss_own_account(state)
    if stopped:
        stats = CacheRunStats(0, 0, 0, stopped)
    else:
        with get_db_connection() as conn:
            stats = _fill_caches(state, conn, now)
    logger.info(f"follow caches: {stats._asdict()}")
    return stats
