"""follow_user / get_user against a mocked SoundCloud API."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from music_minion.domain.library.provider import ProviderConfig, ProviderState
from music_minion.domain.library.providers.soundcloud import api

AUTH = ProviderState(config=ProviderConfig(name="soundcloud"), authenticated=True)
BACKOFF = "music_minion.domain.library.providers.soundcloud.api._request_with_backoff"


def http_error(status: int) -> requests.HTTPError:
    return requests.HTTPError(response=MagicMock(status_code=status, text="nope"))


def test_follow_puts_user_urn() -> None:
    with patch(BACKOFF, return_value=(AUTH, MagicMock())) as request:
        _state, ok = api.follow_user(AUTH, "42")
    assert ok is True
    request.assert_called_once_with(
        AUTH, "PUT", f"{api.API_BASE_URL}/me/followings/soundcloud:users:42"
    )


def test_follow_4xx_is_refusal() -> None:
    with patch(BACKOFF, side_effect=http_error(404)):
        assert api.follow_user(AUTH, "42")[1] is False


def test_follow_5xx_raises() -> None:
    with patch(BACKOFF, side_effect=http_error(500)), pytest.raises(requests.HTTPError):
        api.follow_user(AUTH, "42")


def test_follow_unauthenticated_skips_call() -> None:
    state = ProviderState(config=ProviderConfig(name="soundcloud"))
    with patch(BACKOFF) as request:
        assert api.follow_user(state, "42")[1] is False
    request.assert_not_called()


def test_get_user_returns_profile() -> None:
    response = MagicMock()
    response.json.return_value = {"id": 42, "username": "Wooli"}
    with patch(BACKOFF, return_value=(AUTH, response)) as request:
        assert api.get_user(AUTH, "soundcloud:users:42")[1] == {
            "id": 42,
            "username": "Wooli",
        }
    assert request.call_args.args[2] == f"{api.API_BASE_URL}/users/soundcloud:users:42"


def test_get_user_404_is_none() -> None:
    with patch(BACKOFF, side_effect=http_error(404)):
        assert api.get_user(AUTH, "42")[1] is None
