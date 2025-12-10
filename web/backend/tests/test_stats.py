"""Tests for stats API endpoints."""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from web.backend.main import app
from web.backend.routers.stats import (
    _calculate_avg_comparisons_per_day,
    _estimate_coverage_time,
    _get_genre_stats,
)

client = TestClient(app)


class TestCalculateAvgComparisonsPerDay:
    """Test _calculate_avg_comparisons_per_day helper function."""

    @patch("music_minion.core.database.get_db_connection")
    def test_calculate_avg_comparisons_per_day_with_data(self, mock_get_db):
        """Test calculates average with comparison data."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {
            "comparison_count": 35
        }  # 35 comparisons in 7 days = 5 per day
        mock_conn.execute.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn

        result = _calculate_avg_comparisons_per_day(days=7)
        assert result == 5.0

    @patch("music_minion.core.database.get_db_connection")
    def test_calculate_avg_comparisons_per_day_no_data(self, mock_get_db):
        """Test returns 0 when no comparisons."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {"comparison_count": 0}
        mock_conn.execute.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn

        result = _calculate_avg_comparisons_per_day(days=7)
        assert result == 0.0

    @patch("music_minion.core.database.get_db_connection")
    def test_calculate_avg_comparisons_per_day_zero_days(self, mock_get_db):
        """Test handles zero days gracefully."""
        result = _calculate_avg_comparisons_per_day(days=0)
        assert result == 0.0


class TestEstimateCoverageTime:
    """Test _estimate_coverage_time helper function."""

    def test_estimate_coverage_time_already_complete(self):
        """Test returns 0 when coverage is already 100%."""
        result = _estimate_coverage_time(100.0, 10.0, target=5)
        assert result == 0.0

    def test_estimate_coverage_time_no_comparisons(self):
        """Test returns None when no comparisons happening."""
        result = _estimate_coverage_time(50.0, 0.0, target=5)
        assert result is None

    def test_estimate_coverage_time_partial_coverage(self):
        """Test estimates time for partial coverage."""
        # 50% coverage, 10 comparisons/day, target=5
        # remaining_coverage = 50%, days_needed = (0.5) * (5 / 10) = 0.25
        result = _estimate_coverage_time(50.0, 10.0, target=5)
        assert result == 0.25

    def test_estimate_coverage_time_negative_result(self):
        """Test doesn't return negative days."""
        result = _estimate_coverage_time(99.9, 1000.0, target=5)
        assert result >= 0.0


class TestGetGenreStats:
    """Test _get_genre_stats helper function."""

    @patch("music_minion.core.database.get_db_connection")
    def test_get_genre_stats_with_data(self, mock_get_db):
        """Test returns genre stats with valid data."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {
                "genre": "Rock",
                "track_count": 10,
                "average_rating": 1600.5,
                "total_comparisons": 50,
            },
            {
                "genre": "Jazz",
                "track_count": 5,
                "average_rating": 1550.0,
                "total_comparisons": 25,
            },
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn

        result = _get_genre_stats(limit=10)

        assert len(result) == 2
        assert result[0].genre == "Rock"
        assert result[0].track_count == 10
        assert result[0].average_rating == 1600.5
        assert result[0].total_comparisons == 50

        assert result[1].genre == "Jazz"
        assert result[1].track_count == 5
        assert result[1].average_rating == 1550.0
        assert result[1].total_comparisons == 25

    @patch("music_minion.core.database.get_db_connection")
    def test_get_genre_stats_no_data(self, mock_get_db):
        """Test returns empty list when no genres meet criteria."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor
        mock_get_db.return_value.__enter__.return_value = mock_conn

        result = _get_genre_stats(limit=10)
        assert result == []


class TestStatsEndpoint:
    """Test the /api/stats endpoint."""

    @patch("web.backend.routers.stats.get_ratings_coverage")
    @patch("web.backend.routers.stats.get_leaderboard")
    @patch("web.backend.routers.stats._calculate_avg_comparisons_per_day")
    @patch("web.backend.routers.stats._estimate_coverage_time")
    @patch("web.backend.routers.stats._get_genre_stats")
    def test_get_stats_success(
        self,
        mock_genre_stats,
        mock_estimate_time,
        mock_avg_comparisons,
        mock_leaderboard,
        mock_coverage,
    ):
        """Test successful stats retrieval."""
        # Mock coverage data
        mock_coverage.return_value = {
            "total_comparisons": 100,
            "tracks_with_comparisons": 50,
            "total_tracks": 100,
            "coverage_percent": 50.0,
            "average_comparisons_per_track": 1.0,
            "average_comparisons_per_compared_track": 2.0,
        }

        # Mock leaderboard data
        mock_leaderboard.return_value = [
            {
                "id": 1,
                "title": "Song A",
                "artist": "Artist A",
                "rating": 1600.0,
                "comparison_count": 10,
                "wins": 7,
            }
        ]

        # Mock other functions
        mock_avg_comparisons.return_value = 14.29  # ~100 comparisons / 7 days
        mock_estimate_time.return_value = 2.5
        mock_genre_stats.return_value = []

        response = client.get("/api/stats")

        assert response.status_code == 200
        data = response.json()

        assert data["total_comparisons"] == 100
        assert data["compared_tracks"] == 50
        assert data["total_tracks"] == 100
        assert data["coverage_percent"] == 50.0
        assert data["average_comparisons_per_day"] == 14.29
        assert data["estimated_days_to_coverage"] == 2.5
        assert isinstance(data["top_genres"], list)
        assert isinstance(data["leaderboard"], list)

        # Check leaderboard structure
        assert len(data["leaderboard"]) == 1
        track = data["leaderboard"][0]
        assert track["track_id"] == 1
        assert track["title"] == "Song A"
        assert track["artist"] == "Artist A"
        assert track["rating"] == 1600.0
        assert track["comparison_count"] == 10
        assert track["wins"] == 7
        assert track["losses"] == 3  # 10 - 7
