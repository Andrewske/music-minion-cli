"""Complete (authoritative) fetch of the SoundCloud likes list.

The incremental sync in api.py stops at the first known track and returns
partial results on errors, so it can only ever add likes. Reconciling
unlikes needs the opposite: the full list, plus a clear verdict on whether
it really is the full list. Anything short of every page fetched and parsed
cleanly is reported as incomplete, and incomplete snapshots never delete.

Access levels: /me/likes/tracks filters by `access`. The OpenAPI spec gives
this endpoint the `access_explicit` parameter whose default is
"playable,preview,blocked"; the incremental sync narrows it to "playable",
which hides blocked/preview likes. Here every level is requested explicitly,
so geo-blocked and preview-only likes are listed too. Even if SoundCloud drops
the parameter from a next_href, the endpoint default still covers all three.
"""

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any, NamedTuple

import requests
from loguru import logger

from music_minion.domain.library.providers.soundcloud.like_uploaders import (
    LikeUploader,
    uploaders_by_track,
)

API_BASE_URL = "https://api.soundcloud.com"
LIKES_URL = f"{API_BASE_URL}/me/likes/tracks"
ALL_ACCESS_LEVELS = "playable,preview,blocked"
PAGE_LIMIT = 200
MAX_PAGES = 500  # 100k likes; past this something is looping

HttpGet = Callable[..., Any]


class LikesSnapshot(NamedTuple):
    """Every liked track id SoundCloud returned, and whether that is all of them."""

    ids: frozenset[str]
    complete: bool
    reason: str
    pages: int
    uploaders: Mapping[str, LikeUploader] = MappingProxyType({})
    ordered_ids: tuple[str, ...] = ()  # SC order, newest like first


class _PageResult(NamedTuple):
    ids: list[str]
    next_href: str | None
    error: str | None
    uploaders: dict[str, LikeUploader] | None = None


def _parse_page(data: Any) -> _PageResult:
    """Pull track ids out of one page; any surprise is an error, not a skip."""
    if not isinstance(data, dict) or not isinstance(data.get("collection"), list):
        return _PageResult([], None, "unexpected payload: no collection list")
    ids: list[str] = []
    for item in data["collection"]:
        if not isinstance(item, dict) or item.get("id") in (None, ""):
            return _PageResult([], None, f"unexpected item: {item!r:.80}")
        if item.get("kind", "track") != "track":
            return _PageResult([], None, f"unexpected kind {item.get('kind')!r}")
        ids.append(str(item["id"]))
    next_href = data.get("next_href")
    if next_href is not None and not isinstance(next_href, str):
        return _PageResult([], None, f"unexpected next_href {next_href!r:.80}")
    return _PageResult(
        ids, next_href or None, None, uploaders_by_track(data["collection"])
    )


def _get_page(http_get: HttpGet, url: str, params: dict, token: str) -> Any:
    """GET one page; raises on HTTP errors so the caller can classify them."""
    response = http_get(
        url, params=params, headers={"Authorization": f"OAuth {token}"}, timeout=30
    )
    response.raise_for_status()
    return response.json()


def _http_error_reason(exc: requests.HTTPError) -> str:
    status = exc.response.status_code if exc.response is not None else None
    if status in (401, 403):
        return f"auth error (HTTP {status})"
    return f"HTTP {status} error"


def fetch_all_liked_ids(
    access_token: str, http_get: HttpGet = requests.get
) -> LikesSnapshot:
    """Page through every like. complete=False on any error or odd payload."""
    ids: set[str] = set()
    ordered: list[str] = []
    uploaders: dict[str, LikeUploader] = {}
    url: str | None = LIKES_URL
    params: dict = {
        "limit": PAGE_LIMIT,
        "linked_partitioning": True,
        "access": ALL_ACCESS_LEVELS,
    }
    seen_urls: set[str] = set()
    pages = 0

    def incomplete(reason: str) -> LikesSnapshot:
        logger.warning(f"sc likes full fetch incomplete after {pages} pages: {reason}")
        return LikesSnapshot(
            frozenset(ids), False, reason, pages, uploaders, tuple(ordered)
        )

    while url:
        if pages >= MAX_PAGES or url in seen_urls:
            return incomplete(f"pagination loop at page {pages + 1}")
        seen_urls.add(url)
        try:
            data = _get_page(http_get, url, params, access_token)
        except requests.HTTPError as exc:
            return incomplete(f"{_http_error_reason(exc)} on page {pages + 1}")
        except (requests.RequestException, ValueError) as exc:
            return incomplete(f"{type(exc).__name__} on page {pages + 1}: {exc}")
        pages += 1
        page = _parse_page(data)
        if page.error:
            return incomplete(f"{page.error} on page {pages}")
        ordered.extend(i for i in page.ids if i not in ids)
        ids.update(page.ids)
        uploaders.update(page.uploaders or {})
        url, params = page.next_href, {}

    logger.info(f"sc likes full fetch complete: {len(ids)} likes in {pages} pages")
    return LikesSnapshot(
        frozenset(ids), True, "complete", pages, uploaders, tuple(ordered)
    )
