"""Tests for play-count deduplication within a time window (history.py)."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from music_minion.domain.radio.history import (
    DEFAULT_DEDUP_WINDOW_MINUTES,
    should_skip_duplicate_play,
    start_play,
)


# ---------------------------------------------------------------------------
# should_skip_duplicate_play — pure logic, mocked timestamps
# ---------------------------------------------------------------------------

BASE = datetime(2026, 1, 1, 12, 0, 0)


def test_default_window_in_acceptance_range() -> None:
    """Default window must fall in the 10-30 minute acceptance range."""
    assert 10 <= DEFAULT_DEDUP_WINDOW_MINUTES <= 30


def test_no_prior_play_is_not_duplicate() -> None:
    assert should_skip_duplicate_play(None, BASE, 15) is False


def test_within_window_is_duplicate() -> None:
    assert should_skip_duplicate_play(BASE, BASE + timedelta(minutes=5), 15) is True


def test_just_inside_window_is_duplicate() -> None:
    later = BASE + timedelta(minutes=15) - timedelta(seconds=1)
    assert should_skip_duplicate_play(BASE, later, 15) is True


def test_exactly_at_window_boundary_is_not_duplicate() -> None:
    """Boundary is exclusive: exactly window_minutes later counts as a new play."""
    later = BASE + timedelta(minutes=15)
    assert should_skip_duplicate_play(BASE, later, 15) is False


def test_outside_window_is_not_duplicate() -> None:
    later = BASE + timedelta(minutes=30)
    assert should_skip_duplicate_play(BASE, later, 15) is False


def test_same_instant_is_duplicate() -> None:
    assert should_skip_duplicate_play(BASE, BASE, 15) is True


def test_negative_elapsed_is_not_duplicate() -> None:
    """Clock skew / out-of-order timestamps should not be treated as duplicates."""
    earlier = BASE - timedelta(minutes=1)
    assert should_skip_duplicate_play(BASE, earlier, 15) is False


def test_zero_window_disables_dedup() -> None:
    assert should_skip_duplicate_play(BASE, BASE, 0) is False


def test_negative_window_disables_dedup() -> None:
    assert should_skip_duplicate_play(BASE, BASE, -5) is False


@pytest.mark.parametrize(
    "minutes,window,expected",
    [
        (0, 10, True),
        (9, 10, True),
        (10, 10, False),
        (11, 10, False),
        (29, 30, True),
        (30, 30, False),
    ],
)
def test_window_parametrized(minutes: int, window: int, expected: bool) -> None:
    later = BASE + timedelta(minutes=minutes)
    assert should_skip_duplicate_play(BASE, later, window) is expected


# ---------------------------------------------------------------------------
# start_play — write-time dedup, mocked DB connection
# ---------------------------------------------------------------------------


def _make_conn(last_row) -> MagicMock:
    """Build a mock connection whose first execute() returns `last_row`."""
    conn = MagicMock()
    select_cursor = MagicMock()
    select_cursor.fetchone.return_value = last_row
    insert_cursor = MagicMock()
    insert_cursor.lastrowid = 999
    conn.execute.side_effect = [select_cursor, insert_cursor]
    # Context manager protocol for `with get_radio_db_connection() as conn:`
    cm = MagicMock()
    cm.__enter__.return_value = conn
    cm.__exit__.return_value = False
    return cm, conn


@patch("music_minion.domain.radio.history.get_radio_db_connection")
def test_start_play_inserts_when_no_prior_play(mock_get_conn: MagicMock) -> None:
    cm, conn = _make_conn(last_row=None)
    mock_get_conn.return_value = cm

    result = start_play(track_id=42, now=BASE)

    assert result == 999  # lastrowid from insert
    conn.commit.assert_called_once()
    # Two execute calls: the SELECT for last play, then the INSERT.
    assert conn.execute.call_count == 2
    assert "INSERT INTO radio_history" in conn.execute.call_args_list[1].args[0]


@patch("music_minion.domain.radio.history.get_radio_db_connection")
def test_start_play_skips_insert_within_window(mock_get_conn: MagicMock) -> None:
    last_row = {"id": 7, "started_at": BASE.isoformat()}
    cm, conn = _make_conn(last_row=last_row)
    mock_get_conn.return_value = cm

    result = start_play(track_id=42, now=BASE + timedelta(minutes=5))

    assert result == 7  # reuse existing history id, no new row
    conn.commit.assert_not_called()
    # Only the SELECT ran; no INSERT.
    assert conn.execute.call_count == 1


@patch("music_minion.domain.radio.history.get_radio_db_connection")
def test_start_play_inserts_after_window_expires(mock_get_conn: MagicMock) -> None:
    last_row = {"id": 7, "started_at": BASE.isoformat()}
    cm, conn = _make_conn(last_row=last_row)
    mock_get_conn.return_value = cm

    result = start_play(track_id=42, now=BASE + timedelta(minutes=20))

    assert result == 999  # new insert because outside window
    conn.commit.assert_called_once()
    assert conn.execute.call_count == 2
    assert "INSERT INTO radio_history" in conn.execute.call_args_list[1].args[0]


@patch("music_minion.domain.radio.history.get_radio_db_connection")
def test_start_play_does_not_modify_existing_rows(mock_get_conn: MagicMock) -> None:
    """Forward-only: a skipped duplicate issues no UPDATE/INSERT, only the SELECT."""
    last_row = {"id": 7, "started_at": BASE.isoformat()}
    cm, conn = _make_conn(last_row=last_row)
    mock_get_conn.return_value = cm

    start_play(track_id=42, now=BASE + timedelta(minutes=1))

    executed_sql = " ".join(call.args[0] for call in conn.execute.call_args_list)
    assert "UPDATE" not in executed_sql.upper()
    assert "INSERT" not in executed_sql.upper()
