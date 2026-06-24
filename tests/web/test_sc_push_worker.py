"""Unit tests for the SC push worker classifier and bounded single-retry."""

from unittest.mock import MagicMock

import pytest
import requests

from web.backend import sc_push_worker as worker


# --- classifier: error strings -------------------------------------------------


@pytest.mark.parametrize(
    "err",
    [
        "Network error: connection reset",
        "Request timed out",
        "HTTP 500: internal server error",
        "HTTP 503: service unavailable",
        "Rate limit exceeded (429)",
        "Unexpected error: something",
    ],
)
def test_transient_error_strings(err: str) -> None:
    assert worker._is_transient_error(err) is True


@pytest.mark.parametrize(
    "err",
    [
        "Not authenticated with SoundCloud",
        "Authentication failed (401)",
        "Token expired and refresh failed",
        "Playlist or track not found (404)",
        "Track not found (404): 123",
        "Track already in playlist",
        "Track not in playlist",
        "HTTP 400: bad request",
        "HTTP 422: unprocessable",
    ],
)
def test_permanent_error_strings(err: str) -> None:
    assert worker._is_transient_error(err) is False


def test_none_error_is_not_transient() -> None:
    assert worker._is_transient_error(None) is False


# --- classifier: exceptions ----------------------------------------------------


def _http_error(status: int) -> requests.HTTPError:
    resp = MagicMock()
    resp.status_code = status
    exc = requests.HTTPError("boom")
    exc.response = resp
    return exc


def test_transient_exceptions() -> None:
    assert worker._is_transient_exception(requests.Timeout()) is True
    assert worker._is_transient_exception(requests.ConnectionError()) is True
    assert worker._is_transient_exception(_http_error(500)) is True
    assert worker._is_transient_exception(_http_error(503)) is True


def test_permanent_exceptions() -> None:
    assert worker._is_transient_exception(_http_error(401)) is False
    assert worker._is_transient_exception(_http_error(404)) is False
    assert worker._is_transient_exception(ValueError("x")) is False


# --- bounded single-retry ------------------------------------------------------


def test_success_runs_once(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep = MagicMock()
    monkeypatch.setattr(worker.time, "sleep", sleep)
    handler = MagicMock(return_value=(True, None))

    worker._run_with_retry(handler, "add")

    assert handler.call_count == 1
    sleep.assert_not_called()


def test_permanent_failure_no_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep = MagicMock()
    monkeypatch.setattr(worker.time, "sleep", sleep)
    handler = MagicMock(return_value=(False, "Authentication failed (401)"))

    worker._run_with_retry(handler, "add")

    assert handler.call_count == 1
    sleep.assert_not_called()


def test_transient_failure_retries_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep = MagicMock()
    monkeypatch.setattr(worker.time, "sleep", sleep)
    handler = MagicMock(return_value=(False, "Network error: reset"))

    worker._run_with_retry(handler, "add")

    # Exactly two attempts (one retry), one sleep of RETRY_DELAY_SECONDS.
    assert handler.call_count == 2
    sleep.assert_called_once_with(worker.RETRY_DELAY_SECONDS)


def test_transient_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep = MagicMock()
    monkeypatch.setattr(worker.time, "sleep", sleep)
    handler = MagicMock(side_effect=[(False, "Request timed out"), (True, None)])

    worker._run_with_retry(handler, "add")

    assert handler.call_count == 2
    sleep.assert_called_once_with(worker.RETRY_DELAY_SECONDS)


def test_transient_exception_retries_once(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep = MagicMock()
    monkeypatch.setattr(worker.time, "sleep", sleep)
    handler = MagicMock(side_effect=requests.ConnectionError("down"))

    worker._run_with_retry(handler, "add")

    assert handler.call_count == 2
    sleep.assert_called_once_with(worker.RETRY_DELAY_SECONDS)


def test_permanent_http_exception_no_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep = MagicMock()
    monkeypatch.setattr(worker.time, "sleep", sleep)
    handler = MagicMock(side_effect=_http_error(404))

    worker._run_with_retry(handler, "remove")

    assert handler.call_count == 1
    sleep.assert_not_called()
