"""Ranked follow suggestions from likes and keeps (step 1)."""

import re
from datetime import UTC, datetime
from typing import Any

import requests
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from music_minion.core.database import get_db_connection
from music_minion.domain.library.providers.soundcloud.api import resolve_user_by_slug
from web.backend.follow_suggestions import profile_slug, split_suggestions
from web.backend.queries import follow_suggestions as queries
from web.backend.soundcloud_auth import get_web_provider_state

router = APIRouter(prefix="/api/follow-suggestions", tags=["follow-suggestions"])

MAX_ARTISTS = 200
MAX_LABELS = 100
SC_FOLLOWING_LIMIT = 2000  # SoundCloud refuses follows past this
# An SC user id, or "name:<name_key>" for a credited name with no account yet
_KEY_RE = re.compile(r"^(?:\d+|name:\w+)$")


class LabelBody(BaseModel):
    is_label: bool


class LinkBody(BaseModel):
    url: str


def _valid_key(key: str) -> str:
    if not _KEY_RE.match(key):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid suggestion key {key!r}: expected an SC user id or name:<key>",
        )
    return key


@router.get("")
def get_follow_suggestions() -> dict[str, Any]:
    """Top artists and labels/channels, best score first."""
    with get_db_connection() as conn:
        ranked = queries.compute_ranked(conn)
        following = queries.following_count(conn)
    artists, labels = split_suggestions(ranked, MAX_ARTISTS, MAX_LABELS)
    return {
        "artists": artists,
        "labels": labels,
        "following": {"count": following, "limit": SC_FOLLOWING_LIMIT},
        "generated_at": datetime.now(UTC).isoformat(),
    }


@router.post("/{key}/dismiss")
def dismiss_suggestion(key: str) -> dict[str, bool]:
    """Permanently hide an account (or unresolved name) from suggestions."""
    with get_db_connection() as conn:
        queries.dismiss(conn, _valid_key(key))
    return {"ok": True}


@router.post("/{key}/label")
def set_suggestion_label(key: str, body: LabelBody) -> dict[str, bool]:
    """Move a suggestion between the artists and labels sections."""
    with get_db_connection() as conn:
        queries.set_label_override(conn, _valid_key(key), body.is_label)
    return {"ok": True}


_SHORT_LINK_RE = re.compile(r"^(?:https?://)?on\.soundcloud\.com/\w+", re.IGNORECASE)


def _expand_short_link(url: str) -> str:
    """The SoundCloud app shares on.soundcloud.com links; follow the redirect."""
    if not _SHORT_LINK_RE.match(url.strip()):
        return url
    target = url.strip() if "://" in url else f"https://{url.strip()}"
    try:
        return requests.head(target, allow_redirects=True, timeout=10).url
    except requests.RequestException:
        logger.exception(f"Could not expand SoundCloud short link {url!r}")
        raise HTTPException(status_code=502, detail=f"Could not open {url!r}")


def _resolve_profile(url: str) -> dict[str, Any]:
    """The SC user a pasted profile URL points at, or an HTTPException."""
    slug = profile_slug(_expand_short_link(url))
    if not slug:
        raise HTTPException(
            status_code=422,
            detail=f"Not a SoundCloud profile link: {url!r} (expected soundcloud.com/<artist>)",
        )
    state = get_web_provider_state()
    if not state or not state.authenticated:
        raise HTTPException(status_code=401, detail="SoundCloud not authenticated")
    _state, user, error = resolve_user_by_slug(state, slug)
    if error or not user:
        status = 404 if error and "not found" in error else 502
        raise HTTPException(status_code=status, detail=f"SoundCloud: {error}")
    if user.get("kind") != "user" or not user.get("id"):
        raise HTTPException(
            status_code=422, detail=f"soundcloud.com/{slug} is not an artist profile"
        )
    return user


@router.post("/{key}/link")
def link_suggestion(key: str, body: LinkBody) -> dict[str, Any]:
    """Point an unresolved credited name at the SC account Kevin pasted."""
    if not _valid_key(key).startswith("name:"):
        raise HTTPException(
            status_code=422, detail=f"Only unresolved names can be linked, got {key!r}"
        )
    user = _resolve_profile(body.url)
    with get_db_connection() as conn:
        queries.link_name(conn, key[5:], user)
    return {
        "ok": True,
        "soundcloud_user_id": str(user["id"]),
        "display_name": user.get("username"),
    }
