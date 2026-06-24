"""Tests for command-bar text cursor movement and editing (ticket #29)."""

from music_minion.ui.blessed.state import (
    UIState,
    delete_char_at_cursor,
    delete_char_before_cursor,
    insert_char_at_cursor,
    move_cursor_end,
    move_cursor_home,
    move_cursor_left,
    move_cursor_right,
    set_input_text,
)
from music_minion.ui.blessed.events.keys.normal import (
    _is_editing_command_text,
    handle_normal_mode_key,
)


def _state(text: str = "", cursor: int | None = None) -> UIState:
    s = set_input_text(UIState(), text)
    if cursor is not None:
        s = s.__class__(**{**s.__dict__, "cursor_pos": cursor})
    return s


class TestCursorMovement:
    def test_left_decrements_clamped(self):
        s = move_cursor_left(_state("abc", 0))
        assert s.cursor_pos == 0

    def test_right_increments_clamped(self):
        s = move_cursor_right(_state("abc", 3))
        assert s.cursor_pos == 3

    def test_left_right_roundtrip(self):
        s = move_cursor_left(_state("abc", 2))
        assert s.cursor_pos == 1
        s = move_cursor_right(s)
        assert s.cursor_pos == 2

    def test_home_and_end(self):
        assert move_cursor_home(_state("abc", 2)).cursor_pos == 0
        assert move_cursor_end(_state("abc", 0)).cursor_pos == 3


class TestCursorEditing:
    def test_insert_at_cursor_middle(self):
        s = insert_char_at_cursor(_state("ac", 1), "b")
        assert s.input_text == "abc"
        assert s.cursor_pos == 2

    def test_backspace_before_cursor(self):
        s = delete_char_before_cursor(_state("abc", 2))
        assert s.input_text == "ac"
        assert s.cursor_pos == 1

    def test_backspace_at_start_noop(self):
        s = delete_char_before_cursor(_state("abc", 0))
        assert s.input_text == "abc"
        assert s.cursor_pos == 0

    def test_delete_at_cursor_keeps_position(self):
        s = delete_char_at_cursor(_state("abc", 1))
        assert s.input_text == "ac"
        assert s.cursor_pos == 1

    def test_delete_at_end_noop(self):
        s = delete_char_at_cursor(_state("abc", 3))
        assert s.input_text == "abc"
        assert s.cursor_pos == 3


class TestDisambiguation:
    def test_editing_when_input_present(self):
        assert _is_editing_command_text(_state("abc", 3)) is True

    def test_not_editing_when_empty(self):
        assert _is_editing_command_text(_state("", 0)) is False

    def test_not_editing_when_palette_open(self):
        s = _state("abc", 3)
        s = s.__class__(**{**s.__dict__, "palette_visible": True})
        assert _is_editing_command_text(s) is False


class TestArrowRouting:
    def test_left_moves_cursor_when_editing(self):
        s, cmd = handle_normal_mode_key(_state("abc", 3), {"type": "arrow_left"})
        assert cmd is None
        assert s.cursor_pos == 2

    def test_left_seeks_when_idle(self):
        s, cmd = handle_normal_mode_key(_state("", 0), {"type": "arrow_left"})
        assert cmd is not None
        assert cmd.action == "seek_relative"
        assert cmd.data["seconds"] == -5.0

    def test_right_seeks_when_idle(self):
        s, cmd = handle_normal_mode_key(_state("", 0), {"type": "arrow_right"})
        assert cmd is not None
        assert cmd.action == "seek_relative"
        assert cmd.data["seconds"] == 5.0
