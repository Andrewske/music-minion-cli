"""Follow action and tier review for new follows (step 0)."""

from typing import Any

import requests
from fastapi import APIRouter, HTTPException
from loguru import logger

from music_minion.core.database import get_db_connection
from music_minion.domain.library.provider import ProviderState
from music_minion.domain.library.providers.soundcloud.api import follow_user, get_user
from web.backend.queries.artists import record_new_follow
from web.backend.queries.follow_sync import get_untiered_follows
from web.backend.soundcloud_auth import get_web_provider_state

router = APIRouter(prefix="/api/follow-suggestions", tags=["follow-suggestions"])


@router.get("/untiered")
def list_untiered_follows() -> dict[str, list[dict[str, Any]]]:
    """Followed artists still untiered: {recent, rated}."""
    with get_db_connection() as conn:
        return get_untiered_follows(conn)


def _authenticated_state() -> ProviderState:
    state = get_web_provider_state()
    if not state or not state.authenticated:
        raise HTTPException(status_code=401, detail="SoundCloud not authenticated")
    return state


def _follow_on_soundcloud(state: ProviderState, sc_user_id: str) -> ProviderState:
    """Follow on SC or raise: 502 when SC refuses or errors, 503 when unreachable."""
    try:
        state, ok = follow_user(state, sc_user_id)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        logger.exception(f"SC follow failed for sc_user={sc_user_id}: HTTP {status}")
        raise HTTPException(
            status_code=502, detail=f"SoundCloud returned {status} — try again"
        )
    except (requests.Timeout, requests.ConnectionError):
        logger.exception(f"SC follow unreachable for sc_user={sc_user_id}")
        raise HTTPException(status_code=503, detail="Could not reach SoundCloud")
    if not ok:
        raise HTTPException(
            status_code=502, detail=f"SoundCloud refused to follow user {sc_user_id}"
        )
    return state


def _sc_user_or_stub(state: ProviderState, sc_user_id: str) -> dict[str, Any]:
    """The SC user's profile; just the id if the lookup fails (the follow
    already happened, and the nightly sync fills in the details)."""
    try:
        _state, user = get_user(state, sc_user_id)
    except requests.RequestException:
        logger.exception(f"SC user lookup failed after follow: sc_user={sc_user_id}")
        user = None
    return user or {"id": sc_user_id}


@router.post("/{soundcloud_user_id}/follow")
def follow_account(soundcloud_user_id: str) -> dict[str, Any]:
    """Follow an account on SoundCloud, then record it as followed (tier C)."""
    if not soundcloud_user_id.isdigit():
        raise HTTPException(
            status_code=400, detail=f"Not a SoundCloud user id: {soundcloud_user_id}"
        )
    state = _follow_on_soundcloud(_authenticated_state(), soundcloud_user_id)
    sc_user = _sc_user_or_stub(state, soundcloud_user_id)
    with get_db_connection() as conn:
        artist_id = record_new_follow(conn, sc_user)
        conn.commit()
    return {"ok": True, "discovery_artist_id": artist_id}
