"""Tests for track matching deduplication."""

import pytest

from music_minion.domain.library.deduplication import strip_featuring_artists


class TestStripFeaturingArtists:
    """Tests for strip_featuring_artists function."""

    def test_feat_dot_pattern(self) -> None:
        assert strip_featuring_artists("Song (feat. Artist)") == "Song"

    def test_feat_no_dot_pattern(self) -> None:
        assert strip_featuring_artists("Song (feat Artist)") == "Song"

    def test_ft_dot_pattern(self) -> None:
        assert strip_featuring_artists("Song (ft. Artist)") == "Song"

    def test_ft_no_dot_pattern(self) -> None:
        assert strip_featuring_artists("Song (ft Artist)") == "Song"

    def test_featuring_pattern(self) -> None:
        assert strip_featuring_artists("Song (featuring Artist)") == "Song"

    def test_case_insensitive(self) -> None:
        assert strip_featuring_artists("Song (FEAT. Artist)") == "Song"
        assert strip_featuring_artists("Song (Feat. Artist)") == "Song"
        assert strip_featuring_artists("Song (FT. Artist)") == "Song"

    def test_preserves_other_parentheticals(self) -> None:
        result = strip_featuring_artists("Song (feat. Artist) (Remix)")
        assert result == "Song (Remix)"

    def test_original_bug_case(self) -> None:
        """The case that motivated this fix."""
        result = strip_featuring_artists("Light In The Dark (feat. JIM) (Cyclops Remix)")
        assert result == "Light In The Dark (Cyclops Remix)"

    def test_multiple_artists(self) -> None:
        result = strip_featuring_artists("Song (feat. Artist A & Artist B)")
        assert result == "Song"

    def test_empty_string(self) -> None:
        assert strip_featuring_artists("") == ""

    def test_no_featuring(self) -> None:
        assert strip_featuring_artists("Song (Remix)") == "Song (Remix)"

    def test_square_brackets(self) -> None:
        assert strip_featuring_artists("Song [feat. Artist]") == "Song"
        assert strip_featuring_artists("Song [ft. Artist]") == "Song"
        assert strip_featuring_artists("Song [featuring Artist]") == "Song"

    def test_square_brackets_with_other_parens(self) -> None:
        result = strip_featuring_artists("Song [feat. Artist] (Remix)")
        assert result == "Song (Remix)"

    def test_nested_parens_safe_failure(self) -> None:
        """Nested parens should NOT match - safe failure preserves string."""
        original = "Song (feat. Artist (Stage Name))"
        assert strip_featuring_artists(original) == original

    def test_nested_brackets_safe_failure(self) -> None:
        """Nested brackets should NOT match - safe failure preserves string."""
        original = "Song [feat. Artist [Stage Name]]"
        assert strip_featuring_artists(original) == original
