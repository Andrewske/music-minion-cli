"""Tests for selection helper functions."""

from music_minion.ui.blessed.helpers.selection import _compute_scroll_window


class TestScrollWindow:
    """Test scroll window computation logic."""

    def test_no_scroll_when_fits(self):
        """When all options fit, return full range."""
        start, end = _compute_scroll_window(0, 5, 10)
        assert start == 0
        assert end == 5

    def test_scroll_to_selection_at_start(self):
        """Selected item at start should show from beginning."""
        start, end = _compute_scroll_window(0, 20, 5)
        assert start == 0
        assert end == 5

    def test_scroll_to_selection_at_end(self):
        """Selected item at end should show last items."""
        start, end = _compute_scroll_window(19, 20, 5)
        assert start == 15
        assert end == 20

    def test_scroll_to_selection_in_middle(self):
        """Selected item in middle should be centered."""
        start, end = _compute_scroll_window(10, 20, 5)
        assert start == 8
        assert end == 13

    def test_scroll_handles_small_lists(self):
        """Small lists should not cause issues."""
        start, end = _compute_scroll_window(1, 3, 5)
        assert start == 0
        assert end == 3

    def test_scroll_edge_cases(self):
        """Test edge cases with exact boundaries."""
        # Selection at window boundary
        start, end = _compute_scroll_window(5, 10, 5)
        assert start == 3
        assert end == 8

        # Selection exactly at center
        start, end = _compute_scroll_window(5, 11, 5)
        assert start == 3
        assert end == 8
