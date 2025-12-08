#!/usr/bin/env python3
"""Tests for database functions."""

from music_minion.core.database import get_unique_genres


def test_get_unique_genres():
    """Test get_unique_genres returns list[tuple[str, int]] sorted by count desc."""
    genres = get_unique_genres()

    # Should return a list
    assert isinstance(genres, list)

    # Each item should be a tuple of (str, int)
    for genre, count in genres:
        assert isinstance(genre, str)
        assert isinstance(count, int)
        assert count > 0  # Count should be positive

    # Should be sorted by count descending
    if len(genres) > 1:
        for i in range(len(genres) - 1):
            assert genres[i][1] >= genres[i + 1][1]

    # Should exclude NULL and empty genres (this is tested by the SQL query itself)
    # But we can verify no empty strings in the results
    for genre, _ in genres:
        assert genre.strip() != ""  # No empty or whitespace-only genres
