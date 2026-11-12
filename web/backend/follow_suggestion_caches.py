"""Nightly fill of the follow-suggestion caches (runs from sc_feed_worker).

1. Kevin's own account goes into the dismissals, so it is never suggested.
2. Credited names resolve to SC accounts: local sources (liked-track
   uploaders, discovery_artists) are stored as-is; names with 3+ credits that
   are still unresolved go to SoundCloud user search, up to 100 per run.
   Misses are cached too and retried after 30 days.
3. Activity (followers, avatar, recent uploads/reposts, label heuristic) is
   refreshed for up to 150 candidate accounts per run, each at most weekly.
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
from web.backend.soundcloud_metadata import raw_repost_timestamp

NAME_SEARCH_LIMIT = 100
ACTIVITY_LIMIT = 150
MIN_CREDITS_FOR_SEARCH = 3
MISS_RETRY_DAYS = 30
ACTIVITY_MAX_AGE_DAYS = 7
ACTIVITY_WINDOW_DAYS = 90
ACTIVITY_PAGE = 50
# HTTP 0: no usable token (_request_with_backoff raises without a response)
_STOP_ERRORS = (
    "HTTP 0",
    "HTTP 401",
    "HTTP 429",
    "Authentication failed",
    "Rate limited",
)


class CacheRunStats(NamedTuple):
    names_searched: int
    names_resolved: int
    activity_refreshed: int


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
    """Candidate account ids whose activity is missing or over a week old."""
    cutoff = now - timedelta(days=ACTIVITY_MAX_AGE_DAYS)
    stale = [
        s["key"]
        for s in sorted(ranked, key=lambda s: -s["evidence_score"])
        if s["soundcloud_user_id"]
        and (parse_time(fetched_at.get(s["key"])) or datetime.min.replace(tzinfo=UTC))
        < cutoff
    ]
    return stale[:limit]


def looks_like_label(username: str | None, uploads: list[dict[str, Any]]) -> bool:
    """Most recent uploads credit someone other than the account itself."""
    credits = [
        f"{t.get('metadata_artist') or ''} {t.get('title') or ''}" for t in uploads
    ]
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
            resolved_at = CURRENT_TIMESTAMP""",
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


def dismiss_own_account(state: Any) -> Any:
    """Kevin's own SC account is a permanent dismissal (never suggested)."""
    state, me, error = get_me(state)
    if error or not me or not me.get("id"):
        logger.warning(
            f"follow caches: /me lookup failed ({error}); own account not excluded"
        )
        return state
    with get_db_connection() as conn:
        conn.execute(
            """INSERT INTO follow_suggestion_dismissals (soundcloud_user_id)
            VALUES (?) ON CONFLICT(soundcloud_user_id) DO NOTHING""",
            (str(me["id"]),),
        )
        conn.commit()
    return state


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


def search_names(
    state: Any, names: list[tuple[str, str]]
) -> tuple[Any, dict[str, Resolution]]:
    """SoundCloud user search per name; hits and misses both come back."""
    found: dict[str, Resolution] = {}
    for key, display in names:
        state, users, error = search_users(state, display)
        if error:
            logger.warning(f"follow caches: search for {display!r} failed: {error}")
            if error.startswith(_STOP_ERRORS):
                break
            continue
        match = pick_search_match(users, key)
        found[key] = (
            Resolution(
                str(match["id"]),
                match.get("permalink"),
                match.get("username"),
                "medium",
                "search",
            )
            if match
            else Resolution(None, None, None, "none", "search")
        )
    return state, found


def refresh_activity(
    state: Any, conn: sqlite3.Connection, user_ids: list[str], now: datetime
) -> tuple[Any, int]:
    """One profile + one page of uploads and reposts per account."""
    done = 0
    for user_id in user_ids:
        state, user, error = get_user(state, user_id)
        if error and error.startswith(_STOP_ERRORS):
            logger.warning(f"follow caches: activity stopped at {user_id}: {error}")
            break
        state, uploads, _ = get_user_tracks(
            state, user_id, limit=ACTIVITY_PAGE, max_pages=1
        )
        state, reposts, _ = get_user_reposts(
            state, user_id, limit=ACTIVITY_PAGE, max_pages=1
        )
        _store_activity(conn, user_id, summarize_activity(user, uploads, reposts, now))
        done += 1
    return state, done


def refresh_follow_suggestion_caches(state: Any) -> CacheRunStats:
    """The nightly job: own account, name resolution, activity. May raise;
    the feed worker wraps it."""
    now = datetime.now(UTC)
    state = dismiss_own_account(state)
    with get_db_connection() as conn:
        tracks = load_evidence_tracks(conn)
        store_local_resolutions(conn, tracks, resolved_context(conn, tracks, now))
        ranked = _ranked_now(conn, tracks, now)
        names = names_to_search(ranked, _fresh_misses(conn, now), NAME_SEARCH_LIMIT)
        state, searched = search_names(state, names)
        _store_resolutions(conn, searched)
        ranked = _ranked_now(conn, tracks, now)
        due = accounts_to_refresh(
            ranked, _activity_fetched_at(conn), now, ACTIVITY_LIMIT
        )
        state, refreshed = refresh_activity(state, conn, due, now)
    stats = CacheRunStats(
        len(searched),
        sum(1 for r in searched.values() if r.soundcloud_user_id),
        refreshed,
    )
    logger.info(f"follow caches: {stats._asdict()}")
    return stats
