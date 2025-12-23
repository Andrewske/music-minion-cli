"""
Tests for ELO metadata functions in metadata.py.
"""

import pytest

from music_minion.domain.library.metadata import (
    strip_elo_from_comment,
    format_comment_with_elo,
)


class TestStripEloFromComment:
    """Test stripping ELO rating prefixes from comments."""

    def test_strips_elo_with_separator(self):
        """Test stripping 'NNNN - ' prefix."""
        result = strip_elo_from_comment("1532 - Original comment")
        assert result == "Original comment"

    def test_strips_elo_only(self):
        """Test stripping ELO-only comment."""
        result = strip_elo_from_comment("1532")
        assert result == ""

    def test_preserves_non_elo_comment(self):
        """Test preserving comments without ELO prefix."""
        result = strip_elo_from_comment("No prefix here")
        assert result == "No prefix here"

    def test_handles_none(self):
        """Test handling None input."""
        result = strip_elo_from_comment(None)
        assert result == ""

    def test_handles_empty_string(self):
        """Test handling empty string input."""
        result = strip_elo_from_comment("")
        assert result == ""

    def test_strips_with_extra_spaces(self):
        """Test stripping with extra spaces around separator."""
        result = strip_elo_from_comment("1532  -  Spaced out")
        assert result == "Spaced out"


class TestFormatCommentWithElo:
    """Test formatting comments with ELO rating prefixes."""

    def test_formats_with_comment(self):
        """Test formatting with existing comment."""
        result = format_comment_with_elo(1532, "Great track")
        assert result == "1532 - Great track"

    def test_formats_without_comment(self):
        """Test formatting without existing comment."""
        result = format_comment_with_elo(987, None)
        assert result == "0987"

    def test_zero_pads_low_elo(self):
        """Test zero-padding for low ELO values."""
        result = format_comment_with_elo(42, "Test")
        assert result == "0042 - Test"

    def test_clamps_high_elo(self):
        """Test clamping high ELO values to 9999."""
        result = format_comment_with_elo(99999, "Test")
        assert result == "9999 - Test"

    def test_clamps_negative_elo(self):
        """Test clamping negative ELO values to 0000."""
        result = format_comment_with_elo(-100, "Test")
        assert result == "0000 - Test"

    def test_rounds_float_elo(self):
        """Test rounding float ELO values."""
        result = format_comment_with_elo(1532.7, "Test")
        assert result == "1533 - Test"

    def test_strips_existing_elo_prefix(self):
        """Test stripping existing ELO prefix before adding new one."""
        result = format_comment_with_elo(1600, "1400 - Old rating")
        assert result == "1600 - Old rating"
