"""Regression tests for SoundCloud stream URL resolution error handling."""

from unittest import mock

import pytest

from music_minion.domain.library.providers.soundcloud import api
from music_minion.domain.library.providers.soundcloud.exceptions import (
    TrackUnavailableError,
)


def _auth_state() -> mock.MagicMock:
    state = mock.MagicMock()
    state.authenticated = True
    return state


@pytest.mark.parametrize("status", [403, 404, 410])
def test_resolve_stream_url_raises_on_dead_upstream(status: int) -> None:
    """A 403/404/410 from SoundCloud must propagate TrackUnavailableError.

    Regression: the broad `except Exception` used to swallow this into a None
    return, which surfaced as a 503 and let the dead track loop in the queue.
    """
    resp = mock.MagicMock()
    resp.status_code = status

    with mock.patch.object(
        api, "_ensure_valid_token", return_value=(_auth_state(), {"access_token": "t"})
    ), mock.patch.object(api.requests, "get", return_value=resp):
        with pytest.raises(TrackUnavailableError):
            api.resolve_stream_url(_auth_state(), "2342663888")


def test_resolve_stream_url_returns_none_on_transient_error() -> None:
    """Non-availability failures still return None (not raise)."""
    with mock.patch.object(
        api, "_ensure_valid_token", return_value=(_auth_state(), {"access_token": "t"})
    ), mock.patch.object(api.requests, "get", side_effect=OSError("network")):
        assert api.resolve_stream_url(_auth_state(), "123") is None
