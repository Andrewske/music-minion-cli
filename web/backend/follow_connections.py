"""Connection-based follow suggestions (plan steps 2 and 3).

Two lists, both scored by pure functions over rows loaded once:

- co_credit: unfollowed artists who share song credits (collab, remix, feat)
  with Kevin's S/A/B tier artists, parsed from library track credit strings.
- favorites_follow: accounts followed by several S/A artists, from the
  ``sc_artist_followings`` cache that ``refresh_favorite_followings`` fills.
"""

import math
import re
import sqlite3
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

from loguru import logger

from music_minion.core.database import get_db_connection
from music_minion.domain.library.provider import ProviderState
from music_minion.domain.library.providers.soundcloud.api import get_user_followings
from web.backend.queries.artists import (
    _connection_partners,
    _normalize_name,
    _parse_track_credits,
)
from web.backend.sc_errors import is_service_error

CO_CREDIT_TIER_WEIGHTS = {"S": 3.0, "A": 2.0, "B": 1.0}
RELATION_WEIGHTS = {"collab": 1.0, "remix": 0.8, "feat": 0.6}
# _connection_partners relations -> contract relations
_RELATION_MAP = {
    "collab": "collab",
    "remixed": "remix",
    "remixed_by": "remix",
    "features": "feat",
    "featured_on": "feat",
}
FAVORITE_TIER_WEIGHTS = {"S": 1.5, "A": 1.0}
MIN_CO_CREDIT_SCORE = 2.0
MIN_FAVORITES = 3
TOP_N = 50

FOLLOWINGS_MAX_AGE = timedelta(days=7)
FOLLOWINGS_ARTISTS_PER_RUN = 30
FOLLOWINGS_MAX_PAGES = 10
# The feed worker ticks hourly; one refresh batch per ~night.
FOLLOWINGS_RUN_INTERVAL = timedelta(hours=23)
# A favorite whose fetch failed for account reasons waits this long to retry.
FOLLOWINGS_ERROR_BACKOFF = timedelta(hours=24)

_SLUG_SUFFIX_RE = re.compile(r"(?:music|official|musik|dj|beats|producer)$")
_SLUG_PREFIX_RE = re.compile(r"^(?:dj|its|thisis|iam)")
_TS_FORMAT = "%Y-%m-%d %H:%M:%S"


# ---------------------------------------------------------------------------
# Name keys (shared matching rules from the brief)
# ---------------------------------------------------------------------------


def name_key(name: str | None) -> str:
    """Lowercase alphanumerics only: 'Wooli 🐘' and '▶︎ Wooli ◀︎' -> 'wooli'."""
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def slug_keys(slug: str | None) -> set[str]:
    """Slug key plus variants with common suffixes/prefixes stripped."""
    key = name_key(slug)
    no_suffix = _SLUG_SUFFIX_RE.sub("", key)
    prefixes_off = {_SLUG_PREFIX_RE.sub("", k) for k in (key, no_suffix)}
    return ({key, no_suffix} | prefixes_off) - {""}


def followed_keys(rows: Iterable[dict[str, Any]]) -> set[str]:
    """Name keys of followed accounts: display names, slugs and local aliases."""
    keys: set[str] = set()
    for row in rows:
        keys |= slug_keys(row.get("slug"))
        keys.add(name_key(row.get("display_name")))
        keys |= {name_key(alias) for alias in row.get("aliases", ())}
    keys.discard("")
    return keys


# ---------------------------------------------------------------------------
# Co-credit scoring (pure)
# ---------------------------------------------------------------------------


def _track_credit_norms(artist: str, credits: dict[str, list[str]]) -> set[str]:
    """Every normalized name _connection_partners could match on this track."""
    parts = [artist, *credits["primaries"], *credits["feats"], *credits["remixers"]]
    return {_normalize_name(p) for p in parts} - {""}


def _name_index(top_artists: list[dict[str, Any]]) -> dict[str, list[dict]]:
    """Normalized name -> top artists answering to it."""
    index: dict[str, list[dict]] = {}
    for artist in top_artists:
        for name in artist["names"]:
            index.setdefault(name, []).append(artist)
    return index


def _add_link(
    partners: dict[str, dict], partner: str, artist_id: int, relation: str
) -> None:
    """Record partner<->artist, keeping the strongest relation per artist."""
    key = name_key(partner)
    if not key:
        return
    entry = partners.setdefault(key, {"display_name": partner, "links": {}})
    entry["links"] = _merge_links(entry["links"], {artist_id: relation})


def collect_co_credits(
    tracks: Iterable[dict[str, Any]], top_artists: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Credit partners of the top artists, keyed by partner name key.

    Each track is parsed once; only artists whose names appear in its credits
    run through _connection_partners (the per-artist Connections tab logic).
    """
    index = _name_index(top_artists)
    partners: dict[str, dict[str, Any]] = {}
    for track in tracks:
        artist = track["artist"] or ""
        credits = _parse_track_credits(
            artist, track["title"] or "", track["remix_artist"]
        )
        hits = {
            a["id"]: a
            for n in _track_credit_norms(artist, credits)
            for a in index.get(n, [])
        }
        for top in hits.values():
            for partner, relation in _connection_partners(
                artist, credits, top["names"]
            ):
                _add_link(partners, partner, top["id"], _RELATION_MAP[relation])
    return partners


def score_links(links: dict[int, str], artists_by_id: dict[int, dict]) -> float:
    """Sum over distinct top artists of tier weight x relation weight."""
    return sum(
        CO_CREDIT_TIER_WEIGHTS.get(artists_by_id[aid]["tier"], 0.0)
        * RELATION_WEIGHTS[relation]
        for aid, relation in links.items()
    )


def _merge_links(a: dict[int, str], b: dict[int, str]) -> dict[int, str]:
    merged = dict(a)
    for aid, relation in b.items():
        if (
            aid not in merged
            or RELATION_WEIGHTS[relation] > RELATION_WEIGHTS[merged[aid]]
        ):
            merged[aid] = relation
    return merged


def resolve_partners(
    partners: dict[str, dict[str, Any]], resolutions: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Re-key partners by SC user id when resolved, else 'name:<key>'.

    Two names resolving to one account merge their links and keep every
    name key (``name_keys``), so a decision on any of them still applies.
    """
    resolved: dict[str, dict[str, Any]] = {}
    for key, entry in partners.items():
        res = resolutions.get(key) or {}
        sc_id = res.get("soundcloud_user_id")
        final_key = str(sc_id) if sc_id else f"name:{key}"
        prev = resolved.get(final_key)
        links = _merge_links(prev["links"], entry["links"]) if prev else entry["links"]
        resolved[final_key] = {
            **entry,
            "name_key": key,
            "name_keys": (prev["name_keys"] if prev else frozenset()) | {key},
            "resolution": res,
            "links": links,
        }
    return resolved


def _is_excluded(
    key: str, entry: dict[str, Any], followed: dict[str, set[str]], dismissed: set[str]
) -> bool:
    """Dismissed (by id or any merged name key) or followed: by id when
    resolved, else by name key."""
    if key in dismissed or any(f"name:{k}" in dismissed for k in entry["name_keys"]):
        return True
    sc_id = entry["resolution"].get("soundcloud_user_id")
    if sc_id:
        return str(sc_id) in followed["ids"]
    return entry["name_key"] in followed["keys"]


def _via(artist: dict[str, Any], relation: str) -> dict[str, Any]:
    return {
        "discovery_artist_id": artist["id"],
        "display_name": artist["display_name"],
        "tier": artist["tier"],
        "relation": relation,
    }


def _co_credit_connection(
    key: str, entry: dict, score: float, artists_by_id: dict, activity: dict
) -> dict[str, Any]:
    res = entry["resolution"]
    sc_id = res.get("soundcloud_user_id")
    act = activity.get(str(sc_id), {}) if sc_id else {}
    via = sorted(
        (_via(artists_by_id[aid], rel) for aid, rel in entry["links"].items()),
        key=lambda v: ("SAB".find(v["tier"]), v["display_name"].lower()),
    )
    return {
        "key": key,
        "soundcloud_user_id": str(sc_id) if sc_id else None,
        "display_name": res.get("display_name")
        or act.get("username")
        or entry["display_name"],
        "permalink": res.get("permalink") or act.get("permalink"),
        "avatar_url": act.get("avatar_url"),
        "followers": act.get("followers"),
        "score": round(score, 3),
        "via": via,
    }


def build_co_credit(
    partners: dict[str, dict[str, Any]],
    artists_by_id: dict[int, dict[str, Any]],
    followed: dict[str, set[str]],
    dismissed: set[str],
    activity: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Score resolved partners, drop exclusions and weak links, best first."""
    out = []
    for key, entry in partners.items():
        if _is_excluded(key, entry, followed, dismissed):
            continue
        score = score_links(entry["links"], artists_by_id)
        if score >= MIN_CO_CREDIT_SCORE:
            out.append(
                _co_credit_connection(key, entry, score, artists_by_id, activity)
            )
    return _top(out)


def _top(connections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(connections, key=lambda c: (-c["score"], c["display_name"].lower()))
    return ranked[:TOP_N]


# ---------------------------------------------------------------------------
# Favorites-follow scoring (pure)
# ---------------------------------------------------------------------------


def _group_followees(
    rows: Iterable[dict[str, Any]], favorites: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """followee_id -> {row: latest followee info, followers: {favorite ids}}."""
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        follower = str(row["follower_id"])
        if follower not in favorites:
            continue
        entry = grouped.setdefault(str(row["followee_id"]), {"row": row, "by": set()})
        entry["by"].add(follower)
    return grouped


def favorites_score(weighted_n: float, followers: int | None) -> float:
    """Damp by popularity so accounts every favorite follows don't win."""
    return weighted_n / math.log10((followers or 0) + 10)


def _favorites_connection(
    followee_id: str, entry: dict, favorites: dict, activity: dict
) -> dict[str, Any]:
    row, act = entry["row"], activity.get(followee_id, {})
    followers = row.get("followee_followers")
    followers = followers if followers is not None else act.get("followers")
    by = [favorites[f] for f in entry["by"]]
    weighted = sum(FAVORITE_TIER_WEIGHTS.get(f["tier"], 0.0) for f in by)
    via = sorted(
        (_via(f, "follows") for f in by),
        key=lambda v: ("SA".find(v["tier"]), v["display_name"].lower()),
    )
    return {
        "key": followee_id,
        "soundcloud_user_id": followee_id,
        "display_name": row.get("followee_username")
        or act.get("username")
        or followee_id,
        "permalink": row.get("followee_permalink") or act.get("permalink"),
        "avatar_url": act.get("avatar_url"),
        "followers": followers,
        "score": round(favorites_score(weighted, followers), 3),
        "via": via,
    }


def build_favorites_follow(
    rows: Iterable[dict[str, Any]],
    favorites: dict[str, dict[str, Any]],
    excluded_ids: set[str],
    activity: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Accounts followed by 3+ distinct S/A favorites, minus excluded ids.

    ``favorites`` maps SC user id -> top artist; ``excluded_ids`` holds Kevin's
    follows, dismissals and Kevin himself.
    """
    out = [
        _favorites_connection(fid, entry, favorites, activity)
        for fid, entry in _group_followees(rows, favorites).items()
        if fid not in excluded_ids and len(entry["by"]) >= MIN_FAVORITES
    ]
    return _top(out)


# ---------------------------------------------------------------------------
# Loading (DB)
# ---------------------------------------------------------------------------


def _load_top_artists(conn: sqlite3.Connection, tiers: tuple[str, ...]) -> list[dict]:
    """Followed artists in ``tiers`` with every name they answer to in credits."""
    marks = ",".join("?" for _ in tiers)
    rows = conn.execute(
        f"""SELECT id, display_name, tier, soundcloud_user_id FROM discovery_artists
            WHERE is_following = 1 AND tier IN ({marks})""",
        tiers,
    ).fetchall()
    aliases = _aliases_by_artist(conn)
    return [
        {
            **dict(r),
            "names": (
                {_normalize_name(r["display_name"] or "")} | aliases.get(r["id"], set())
            )
            - {""},
        }
        for r in rows
    ]


def _aliases_by_artist(conn: sqlite3.Connection) -> dict[int, set[str]]:
    aliases: dict[int, set[str]] = {}
    for r in conn.execute(
        "SELECT local_name, discovery_artist_id FROM artist_match_resolved"
    ):
        aliases.setdefault(r["discovery_artist_id"], set()).add(r["local_name"])
    return aliases


def _load_followed(conn: sqlite3.Connection) -> dict[str, set[str]]:
    """Followed SC ids and name keys (display name, slug variants, aliases)."""
    rows = conn.execute(
        "SELECT id, soundcloud_user_id, slug, display_name FROM discovery_artists"
        " WHERE is_following = 1"
    ).fetchall()
    aliases = _aliases_by_artist(conn)
    return {
        "ids": {str(r["soundcloud_user_id"]) for r in rows if r["soundcloud_user_id"]},
        "keys": followed_keys(
            {**dict(r), "aliases": aliases.get(r["id"], ())} for r in rows
        ),
    }


def _load_dismissed(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT soundcloud_user_id FROM follow_suggestion_dismissals")
    return {str(r[0]) for r in rows}


def _load_resolutions(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT name_key, soundcloud_user_id, permalink, display_name"
        " FROM sc_name_resolutions WHERE soundcloud_user_id IS NOT NULL"
    )
    return {r["name_key"]: dict(r) for r in rows}


def _load_activity(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT soundcloud_user_id, permalink, username, avatar_url, followers"
        " FROM sc_account_activity"
    )
    return {str(r["soundcloud_user_id"]): dict(r) for r in rows}


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def compute_co_credit(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Top co-credit suggestions across S/A/B artists."""
    top_artists = _load_top_artists(conn, ("S", "A", "B"))
    tracks = conn.execute("SELECT title, artist, remix_artist FROM tracks")
    partners = collect_co_credits(tracks, top_artists)
    resolved = resolve_partners(partners, _load_resolutions(conn))
    return build_co_credit(
        resolved,
        {a["id"]: a for a in top_artists},
        _load_followed(conn),
        _load_dismissed(conn),
        _load_activity(conn),
    )


def compute_favorites_follow(
    conn: sqlite3.Connection, self_user_id: str | None = None
) -> list[dict[str, Any]]:
    """Top accounts followed by Kevin's S/A artists."""
    favorites = {
        str(a["soundcloud_user_id"]): a
        for a in _load_top_artists(conn, ("S", "A"))
        if a["soundcloud_user_id"]
    }
    excluded = _load_followed(conn)["ids"] | _load_dismissed(conn)
    if self_user_id:
        excluded.add(str(self_user_id))
    rows = [dict(r) for r in conn.execute("SELECT * FROM sc_artist_followings")]
    return build_favorites_follow(rows, favorites, excluded, _load_activity(conn))


def compute_connections(self_user_id: str | None = None) -> dict[str, list[dict]]:
    """Both connection lists for GET /api/follow-suggestions/connections."""
    with get_db_connection() as conn:
        return {
            "co_credit": compute_co_credit(conn),
            "favorites_follow": compute_favorites_follow(conn, self_user_id),
        }


# ---------------------------------------------------------------------------
# Followings-of-favorites refresh (feed worker job)
# ---------------------------------------------------------------------------


def _parse_ts(value: str | None) -> datetime | None:
    try:
        return datetime.strptime(value[:19], _TS_FORMAT) if value else None
    except ValueError:
        return None


def _backed_off(failed_at: dict[str, str | None], now: datetime) -> set[str]:
    """Favorites whose last account-level failure is under a day old."""
    retry_cutoff = now - FOLLOWINGS_ERROR_BACKOFF
    return {
        fid
        for fid, value in failed_at.items()
        if (ts := _parse_ts(value)) is not None and ts > retry_cutoff
    }


def stale_favorites(
    favorite_ids: list[str],
    fetched_at: dict[str, str | None],
    now: datetime,
    failed_at: dict[str, str | None] | None = None,
) -> list[str]:
    """Favorites never fetched or older than 7 days: never-fetched first, capped.

    A favorite that failed for account reasons in the last 24h is skipped,
    so it neither burns a call every tick nor blocks the ones behind it."""
    cutoff = now - FOLLOWINGS_MAX_AGE
    skip = _backed_off(failed_at or {}, now)
    ages = {fid: _parse_ts(fetched_at.get(fid)) for fid in favorite_ids}
    stale = [
        fid
        for fid, ts in ages.items()
        if (ts is None or ts < cutoff) and fid not in skip
    ]
    stale.sort(key=lambda fid: ages[fid] or datetime.min)
    return stale[:FOLLOWINGS_ARTISTS_PER_RUN]


def refresh_due(last_fetched_at: str | None, now: datetime) -> bool:
    """One batch per night: skip when anything was fetched in the last 23h."""
    last = _parse_ts(last_fetched_at)
    return last is None or now - last >= FOLLOWINGS_RUN_INTERVAL


def _followee_rows(
    follower_id: str, users: list[dict[str, Any]], fetched_at: str
) -> list[tuple]:
    return [
        (
            follower_id,
            str(u["id"]),
            u.get("permalink"),
            u.get("username"),
            u.get("followers_count"),
            fetched_at,
        )
        for u in users
        if u.get("id") is not None
    ]


def _replace_followings(
    conn: sqlite3.Connection, follower_id: str, rows: list[tuple], fetched_at: str
) -> None:
    """Swap one favorite's followings and stamp its refresh state, in a
    single transaction. The stamp is written even when it follows nobody."""
    conn.execute(
        "DELETE FROM sc_artist_followings WHERE follower_id = ?", (follower_id,)
    )
    conn.executemany(
        """INSERT OR REPLACE INTO sc_artist_followings
           (follower_id, followee_id, followee_permalink, followee_username,
            followee_followers, fetched_at) VALUES (?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.execute(
        """INSERT INTO sc_favorite_followings_state
               (follower_id, fetched_at, followee_count, status)
           VALUES (?, ?, ?, 'ok')
           ON CONFLICT(follower_id) DO UPDATE SET fetched_at = excluded.fetched_at,
               followee_count = excluded.followee_count, status = excluded.status,
               last_error_at = NULL, last_error = NULL""",
        (follower_id, fetched_at, len(rows)),
    )
    conn.commit()


def _record_failure(
    conn: sqlite3.Connection, follower_id: str, error: str, failed_at: str
) -> None:
    """Back one favorite off after an account-level failure. Its followee rows
    and fetched_at stay as they were, so it is still stale, just not retried
    until the backoff passes."""
    conn.execute(
        """INSERT INTO sc_favorite_followings_state
               (follower_id, status, last_error_at, last_error)
           VALUES (?, 'error', ?, ?)
           ON CONFLICT(follower_id) DO UPDATE SET status = excluded.status,
               last_error_at = excluded.last_error_at,
               last_error = excluded.last_error""",
        (follower_id, failed_at, error[:500]),
    )
    conn.commit()


def _refresh_plan(conn: sqlite3.Connection, now: datetime) -> list[str]:
    """Favorites to fetch this run, or [] when a batch already ran tonight.

    Freshness comes from sc_favorite_followings_state, so a favorite that
    follows nobody counts as fetched instead of being retried every tick.
    A batch that only hit account-level failures also counts as tonight's."""
    (last,) = conn.execute(
        """SELECT MAX(ts) FROM (
               SELECT fetched_at AS ts FROM sc_favorite_followings_state
               UNION ALL SELECT last_error_at FROM sc_favorite_followings_state)"""
    ).fetchone()
    if not refresh_due(last, now):
        return []
    state = conn.execute(
        "SELECT follower_id, fetched_at, last_error_at FROM sc_favorite_followings_state"
    ).fetchall()
    favorites = [
        str(a["soundcloud_user_id"])
        for a in _load_top_artists(conn, ("S", "A"))
        if a["soundcloud_user_id"]
    ]
    fetched = {r["follower_id"]: r["fetched_at"] for r in state}
    failed = {r["follower_id"]: r["last_error_at"] for r in state}
    return stale_favorites(favorites, fetched, now, failed)


def _refresh_one(
    state: ProviderState, conn: sqlite3.Connection, follower_id: str, now: datetime
) -> tuple[ProviderState, bool, str | None]:
    """Fetch one favorite's followings: (state, stored, service error to stop on).

    An account-level error (incomplete pagination, 404 or other 4xx, a
    malformed payload) backs this favorite off and lets the batch go on."""
    state, users, error = get_user_followings(
        state, follower_id, max_pages=FOLLOWINGS_MAX_PAGES
    )
    stamp = now.strftime(_TS_FORMAT)
    if error and is_service_error(error):
        logger.warning(f"favorite followings stopped at {follower_id}: {error}")
        return state, False, error
    if error:
        logger.warning(f"favorite followings skipped {follower_id}: {error}")
        _record_failure(conn, follower_id, error, stamp)
        return state, False, None
    _replace_followings(
        conn, follower_id, _followee_rows(follower_id, users, stamp), stamp
    )
    return state, True, None


def refresh_favorite_followings(
    state: ProviderState, now: datetime
) -> tuple[ProviderState, int]:
    """Fetch followings for up to 30 stale S/A favorites; returns artists refreshed.

    A service-wide error (5xx, 429, auth, no token, network) stops the run so
    an outage costs one call, not thirty; that artist is retried next tick.
    An account-level error skips just that artist, backed off for a day.
    """
    with get_db_connection() as conn:
        plan = _refresh_plan(conn, now)
        refreshed = 0
        for follower_id in plan:
            state, stored, stop = _refresh_one(state, conn, follower_id, now)
            refreshed += stored
            if stop:
                break
    if plan:
        logger.info(f"favorite followings: refreshed {refreshed}/{len(plan)} artists")
    return state, refreshed
