"""Unfollow suggestions: followed SoundCloud accounts that add little.

Pure functions only; the DB reads live in queries/unfollow_suggestions.py.

A "find" is a liked or kept track the feed only showed because of this
account: one it uploaded, or one it reposted that no other followed account
reposted or uploaded.

    value = sum over finds of recency_weight (the follow side's)
    noise = feed items per month since max(feed start, followed_at)

Rank lowest value first, ties by most noise.
"""

import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any, NamedTuple

from web.backend.follow_suggestions import LABEL_NAME_RE, recency_weight
from web.backend.soundcloud_metadata import parse_soundcloud_datetime as parse_time

SECTIONS = ("redundant", "dormant", "labels", "low_yield")
REDUNDANT_MIN_ITEMS = 50  # a feed this busy with <= 1 find is pure overlap
REDUNDANT_MAX_FINDS = 1
RECENT_FOLLOW_DAYS = 30  # too new to judge
LOW_YIELD_MAX = 200
DAYS_PER_MONTH = 30.44

# The follow side's label words plus promo / repost channels
_EXTRA_LABEL_RE = re.compile(r"promo|repost", re.IGNORECASE)


class FollowedAccount(NamedTuple):
    discovery_artist_id: int
    soundcloud_user_id: str | None
    display_name: str | None
    slug: str
    avatar_url: str | None
    followers: int | None
    tier: str | None
    followed_at: str | None
    polled: bool  # uploads checked at least once
    reposts: int
    uploads: int
    last_item_at: str | None


class GoodItem(NamedTuple):
    """A liked or kept track some followed account reposted or uploaded."""

    discovery_artist_id: int
    soundcloud_id: str
    kind: str  # 'upload' | 'repost'
    item_at: str | None  # when it reached the feed
    liked_at: str | None  # like time, or decided_at for keep-only tracks
    like_order: int | None


def is_label_name(display_name: str | None, slug: str | None) -> bool:
    """Name reads like a label, collective, promo or repost channel."""
    text = f"{display_name or ''} {slug or ''}"
    return bool(LABEL_NAME_RE.search(text) or _EXTRA_LABEL_RE.search(text))


def is_eligible(account: FollowedAccount, now: datetime) -> bool:
    """Polled at least once and followed more than 30 days ago (or unknown)."""
    if not account.polled:
        return False
    followed = parse_time(account.followed_at)
    return followed is None or now - followed > timedelta(days=RECENT_FOLLOW_DAYS)


def history_months(
    followed_at: str | None, feed_start: datetime, now: datetime
) -> float:
    """Months this account has been in the feed history, at least one."""
    followed = parse_time(followed_at)
    start = max(feed_start, followed) if followed else feed_start
    return max(1.0, (now - start).days / DAYS_PER_MONTH)


def latest(times: Iterable[str | None]) -> str | None:
    """The newest of mixed-format SC/ISO timestamps, as ISO 8601 (UTC)."""
    parsed = [when for when in map(parse_time, times) if when is not None]
    return max(parsed).isoformat() if parsed else None


def _merge(items: list[GoodItem]) -> GoodItem:
    """One account's rows for one track: an upload beats a repost."""
    kind = "upload" if any(i.kind == "upload" for i in items) else "repost"
    times = [i.item_at for i in items if i.item_at]
    return items[0]._replace(kind=kind, item_at=min(times) if times else None)


def find_items(items: Iterable[GoodItem]) -> tuple[list[GoodItem], Counter[int]]:
    """(finds, good tracks per account) from every followed account's items.

    A find is an account's own upload, or a repost no other account carried.
    """
    grouped: dict[tuple[int, str], list[GoodItem]] = defaultdict(list)
    for item in items:
        grouped[(item.discovery_artist_id, item.soundcloud_id)].append(item)
    carriers = Counter(sc_id for _artist, sc_id in grouped)
    merged = [_merge(group) for group in grouped.values()]
    finds = [m for m in merged if m.kind == "upload" or carriers[m.soundcloud_id] == 1]
    return finds, Counter(m.discovery_artist_id for m in merged)


def score_account(
    account: FollowedAccount,
    finds: Iterable[GoodItem],
    good: int,
    feed_start: datetime,
    now: datetime,
) -> dict[str, Any]:
    """The account's row: identity, feed counts, finds, value and noise."""
    finds = list(finds)
    items = account.reposts + account.uploads
    months = history_months(account.followed_at, feed_start, now)
    value = sum(recency_weight(f.liked_at, now, f.like_order) for f in finds)
    return {
        **{k: getattr(account, k) for k in _IDENTITY_FIELDS},
        "items": items,
        "reposts": account.reposts,
        "uploads": account.uploads,
        "good": good,
        "unique_finds": sum(f.kind == "repost" for f in finds),
        "liked_uploads": sum(f.kind == "upload" for f in finds),
        "value": round(value, 3),
        "noise_per_month": round(items / months, 1),
        "last_find_at": latest(f.item_at for f in finds),
        "last_item_at": account.last_item_at,
    }


_IDENTITY_FIELDS = (
    "discovery_artist_id", "soundcloud_user_id", "display_name", "slug",
    "avatar_url", "followers", "tier", "followed_at",
)  # fmt: skip


def section_of(row: dict[str, Any]) -> str:
    """First matching section: redundant, dormant, labels, else low_yield."""
    if row["items"] == 0:
        return "dormant"
    if (
        row["items"] >= REDUNDANT_MIN_ITEMS
        and row["unique_finds"] <= REDUNDANT_MAX_FINDS
        and row["liked_uploads"] == 0
    ):
        return "redundant"
    if is_label_name(row["display_name"], row["slug"]):
        return "labels"
    return "low_yield"


def _by_noise(row: dict[str, Any]) -> tuple[float, str]:
    return (-row["noise_per_month"], (row["display_name"] or row["slug"]).lower())


def _by_value(row: dict[str, Any]) -> tuple[float, float, str]:
    return (row["value"], *_by_noise(row))


def _rows_by_section(
    accounts: Iterable[FollowedAccount],
    good_items: Iterable[GoodItem],
    feed_start: datetime,
    now: datetime,
) -> dict[str, list[dict[str, Any]]]:
    finds, good = find_items(good_items)
    finds_by: dict[int, list[GoodItem]] = defaultdict(list)
    for f in finds:
        finds_by[f.discovery_artist_id].append(f)
    sections: dict[str, list[dict[str, Any]]] = {s: [] for s in SECTIONS}
    for account in (a for a in accounts if is_eligible(a, now)):
        artist_id = account.discovery_artist_id
        row = score_account(
            account, finds_by[artist_id], good[artist_id], feed_start, now
        )
        sections[section_of(row)].append(row)
    return sections


def build_sections(
    accounts: Iterable[FollowedAccount],
    good_items: Iterable[GoodItem],
    feed_start: datetime,
    now: datetime,
) -> dict[str, list[dict[str, Any]]]:
    """Eligible accounts split into sections, each in display order.

    good_items must cover every followed account (kept ones too), since
    another account carrying a track is what makes a repost redundant.
    """
    sections = _rows_by_section(accounts, good_items, feed_start, now)
    return {
        "redundant": sorted(sections["redundant"], key=_by_noise),
        "dormant": sorted(sections["dormant"], key=_by_noise),
        "labels": sorted(sections["labels"], key=_by_value),
        "low_yield": sorted(sections["low_yield"], key=_by_value)[:LOW_YIELD_MAX],
    }
