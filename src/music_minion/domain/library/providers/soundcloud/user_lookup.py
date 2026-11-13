"""Read-only SoundCloud user lookups for follow suggestions.

User search (name -> account), a single user's profile, and /me. All go
through api._request_with_backoff for token refresh and 429/5xx retries.
"""

import json
from typing import Any

import requests
from requests.exceptions import HTTPError

from ...provider import ProviderState
from .api import API_BASE_URL, _request_with_backoff


def _get_json(
    state: ProviderState, url: str, params: dict[str, Any] | None = None
) -> tuple[ProviderState, Any, str | None]:
    """GET one JSON document; errors come back as a message, never raised."""
    try:
        state, response = _request_with_backoff(state, "GET", url, params=params)
        return state, response.json(), None
    except HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 0
        return state, None, f"HTTP {status}"
    except requests.exceptions.RequestException as exc:
        return state, None, f"{type(exc).__name__}"
    except (json.JSONDecodeError, ValueError):
        return state, None, "Invalid JSON response"


def search_users(
    state: ProviderState, query: str, limit: int = 20
) -> tuple[ProviderState, list[dict[str, Any]], str | None]:
    """GET /users?q=<query>: one page of matching user dicts."""
    params = {"q": query, "limit": min(limit, 50), "linked_partitioning": "true"}
    state, data, error = _get_json(state, f"{API_BASE_URL}/users", params)
    if error:
        return state, [], error
    users = data if isinstance(data, list) else (data or {}).get("collection") or []
    return state, [u for u in users if isinstance(u, dict)], None


def get_user(
    state: ProviderState, user_id: str
) -> tuple[ProviderState, dict[str, Any] | None, str | None]:
    """GET /users/soundcloud:users:<id>: profile with followers_count, avatar_url."""
    url = f"{API_BASE_URL}/users/soundcloud:users:{user_id}"
    state, data, error = _get_json(state, url)
    return state, data if isinstance(data, dict) else None, error


def get_me(
    state: ProviderState,
) -> tuple[ProviderState, dict[str, Any] | None, str | None]:
    """GET /me: the authenticated account (Kevin's own)."""
    state, data, error = _get_json(state, f"{API_BASE_URL}/me")
    return state, data if isinstance(data, dict) else None, error
