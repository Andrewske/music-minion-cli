"""Regression tests for SoundCloud stream URL resolution error handling."""

from typing import Any
from unittest import mock

import pytest
import requests

from music_minion.domain.library.providers.soundcloud import api
from music_minion.domain.library.providers.soundcloud.exceptions import (
    TrackUnavailableError,
)


def _auth_state() -> mock.MagicMock:
    state = mock.MagicMock()
    state.authenticated = True
    return state


def _response(
    status: int, json_data: dict | None = None, headers: dict | None = None
) -> mock.MagicMock:
    resp = mock.MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    if json_data is not None:
        resp.json.return_value = json_data
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    else:
        resp.raise_for_status.return_value = None
    return resp


def _patch_token() -> Any:
    return mock.patch.object(
        api, "_ensure_valid_token", return_value=(_auth_state(), {"access_token": "t"})
    )


@pytest.mark.parametrize("status", [403, 404, 410])
def test_resolve_stream_url_raises_on_dead_upstream(status: int) -> None:
    """A 403/404/410 from SoundCloud must propagate TrackUnavailableError.

    Regression: the broad `except Exception` used to swallow this into a None
    return, which surfaced as a 503 and let the dead track loop in the queue.
    """
    with (
        _patch_token(),
        mock.patch.object(api.requests, "request", return_value=_response(status)),
    ):
        with pytest.raises(TrackUnavailableError):
            api.resolve_stream_url(_auth_state(), "2342663888")


def test_resolve_stream_url_returns_none_on_transient_error() -> None:
    """Non-availability failures still return None (not raise)."""
    with (
        _patch_token(),
        mock.patch.object(api.requests, "request", side_effect=OSError("network")),
    ):
        assert api.resolve_stream_url(_auth_state(), "123") is None


def test_resolve_stream_url_retries_429_then_succeeds() -> None:
    """A 429 on the streams call is retried with backoff, not treated as fatal."""
    responses = [
        _response(429),
        _response(200, json_data={"http_mp3_128_url": "https://sc/stream"}),
        _response(302, headers={"Location": "https://cdn/track.mp3"}),
    ]
    with (
        _patch_token(),
        mock.patch.object(api.requests, "request", side_effect=responses),
        mock.patch.object(api.time, "sleep") as sleep_mock,
    ):
        result = api.resolve_stream_url(_auth_state(), "123")

    assert result == "https://cdn/track.mp3"
    sleep_mock.assert_called_once_with(2)


def test_resolve_stream_url_429_exhaustion_returns_none() -> None:
    """429 on every attempt exhausts retries and returns None (endpoint 503s)."""
    with (
        _patch_token(),
        mock.patch.object(api.requests, "request", return_value=_response(429)),
        mock.patch.object(api.time, "sleep"),
    ):
        assert api.resolve_stream_url(_auth_state(), "123") is None
