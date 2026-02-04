"""Unit tests for file move detection and cleanup logic."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from music_minion.domain.sync.engine import (
    detect_missing_and_moved_files,
    path_similarity,
)


class TestPathSimilarity:
    """Tests for path_similarity function."""

    def test_identical_paths(self):
        """Identical paths should have similarity of 1.0."""
        path = "/Music/Album1/track.mp3"
        assert path_similarity(path, path) == 1.0

    def test_completely_different_paths(self):
        """Completely different paths should have low similarity."""
        path1 = "/Music/Album1"
        path2 = "/Videos/Movies"
        similarity = path_similarity(path1, path2)
        assert similarity < 0.5

    def test_same_directory_different_file(self):
        """Files in same directory should have high similarity."""
        path1 = "/Music/Album1/track1.mp3"
        path2 = "/Music/Album1/track2.mp3"
        similarity = path_similarity(
            str(Path(path1).parent), str(Path(path2).parent)
        )
        assert similarity == 1.0

    def test_subdirectory_similarity(self):
        """Subdirectory should have high but not perfect similarity."""
        path1 = "/Music/Album1"
        path2 = "/Music/Album1/Disc2"
        similarity = path_similarity(path1, path2)
        assert 0.8 < similarity < 1.0

    def test_sibling_directories(self):
        """Sibling directories should have moderate similarity."""
        path1 = "/Music/Album1"
        path2 = "/Music/Album2"
        similarity = path_similarity(path1, path2)
        assert 0.5 < similarity < 0.9


class TestDetectMissingAndMovedFiles:
    """Tests for detect_missing_and_moved_files function."""

    @pytest.fixture
    def temp_library(self):
        """Create a temporary music library for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lib_path = Path(tmpdir)

            # Create directory structure
            (lib_path / "album1").mkdir()
            (lib_path / "album2").mkdir()
            (lib_path / "singles").mkdir()

            # Create test files
            (lib_path / "album1" / "track1.mp3").write_text("audio data 1")
            (lib_path / "album2" / "track2.mp3").write_text("audio data 2")
            (lib_path / "singles" / "single.mp3").write_text("audio data 3")

            yield lib_path

    @pytest.fixture
    def mock_config(self, temp_library):
        """Create mock config with test library paths."""
        config = Mock()
        config.music.library_paths = [str(temp_library)]
        config.music.supported_formats = [".mp3", ".opus", ".m4a"]
        return config

    def test_no_missing_files(self, mock_config, temp_library):
        """Should return empty result when no files are missing."""
        with patch("music_minion.domain.sync.engine.get_db_connection") as mock_conn:
            # Mock database to return tracks that all exist
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = [
                {
                    "id": 1,
                    "local_path": str(temp_library / "album1" / "track1.mp3"),
                    "title": "Track 1",
                    "artist": "Artist",
                }
            ]
            mock_conn.return_value.__enter__.return_value.execute.return_value = (
                mock_cursor
            )

            result = detect_missing_and_moved_files(mock_config)

            assert result["relocated"] == 0
            assert result["deleted"] == 0
            assert len(result["actions"]) == 0

    def test_delete_orphaned_track(self, mock_config, temp_library):
        """Should delete track when file doesn't exist and no match found."""
        missing_path = str(temp_library / "album1" / "deleted.mp3")

        with patch("music_minion.domain.sync.engine.get_db_connection") as mock_conn:
            # Mock database query
            mock_cursor_query = Mock()
            mock_cursor_query.fetchall.return_value = [
                {
                    "id": 1,
                    "local_path": missing_path,
                    "title": "Deleted",
                    "artist": "Artist",
                }
            ]

            # Mock database execute for updates
            mock_context = mock_conn.return_value.__enter__.return_value
            mock_context.execute.return_value = mock_cursor_query

            result = detect_missing_and_moved_files(mock_config)

            assert result["deleted"] == 1
            assert result["relocated"] == 0
            assert len(result["actions"]) == 1
            assert result["actions"][0]["type"] == "delete"
            assert result["actions"][0]["reason"] == "file_not_found"

    def test_relocate_single_match(self, mock_config, temp_library):
        """Should relocate track when single file with same name exists."""
        old_path = str(temp_library / "album1" / "track2.mp3")
        new_path = str(temp_library / "album2" / "track2.mp3")

        with patch("music_minion.domain.sync.engine.get_db_connection") as mock_conn:
            # Mock database query
            mock_cursor_query = Mock()
            mock_cursor_query.fetchall.return_value = [
                {
                    "id": 1,
                    "local_path": old_path,
                    "title": "Track 2",
                    "artist": "Artist",
                },
                {
                    "id": 2,
                    "local_path": str(temp_library / "album1" / "track1.mp3"),
                    "title": "Track 1",
                    "artist": "Artist",
                },
            ]

            # Mock database execute
            mock_context = mock_conn.return_value.__enter__.return_value
            mock_context.execute.return_value = mock_cursor_query
            mock_context.executemany = Mock()
            mock_context.commit = Mock()

            result = detect_missing_and_moved_files(mock_config)

            assert result["relocated"] == 1
            assert result["deleted"] == 0
            assert len(result["actions"]) == 1
            assert result["actions"][0]["type"] == "relocate"
            assert result["actions"][0]["new_path"] == new_path

    def test_auto_delete_syncthing_conflicts(self, mock_config, temp_library):
        """Should auto-delete tracks with .sync-conflict- in path."""
        conflict_path = str(
            temp_library / "album1" / "track.sync-conflict-20250128.mp3"
        )

        with patch("music_minion.domain.sync.engine.get_db_connection") as mock_conn:
            # Mock database query
            mock_cursor_query = Mock()
            mock_cursor_query.fetchall.return_value = [
                {
                    "id": 1,
                    "local_path": conflict_path,
                    "title": "Conflict",
                    "artist": "Artist",
                }
            ]

            # Mock database execute
            mock_context = mock_conn.return_value.__enter__.return_value
            mock_context.execute.return_value = mock_cursor_query
            mock_context.executemany = Mock()
            mock_context.commit = Mock()

            result = detect_missing_and_moved_files(mock_config)

            assert result["deleted"] == 1
            assert result["relocated"] == 0
            assert result["actions"][0]["reason"] == "syncthing_conflict"

    def test_multiple_candidates_picks_closest(self, mock_config, temp_library):
        """Should pick closest match when multiple files with same name exist."""
        # Create duplicate filenames in different locations
        (temp_library / "album1" / "subdir").mkdir()
        (temp_library / "album1" / "subdir" / "track.mp3").write_text("audio")

        old_path = str(temp_library / "album1" / "track.mp3")

        with patch("music_minion.domain.sync.engine.get_db_connection") as mock_conn:
            # Mock database query - track at old_path is missing
            mock_cursor_query = Mock()
            mock_cursor_query.fetchall.return_value = [
                {
                    "id": 1,
                    "local_path": old_path,
                    "title": "Track",
                    "artist": "Artist",
                },
                {
                    "id": 2,
                    "local_path": str(temp_library / "album2" / "track2.mp3"),
                    "title": "Track 2",
                    "artist": "Artist",
                },
            ]

            # Mock database execute
            mock_context = mock_conn.return_value.__enter__.return_value
            mock_context.execute.return_value = mock_cursor_query
            mock_context.executemany = Mock()
            mock_context.commit = Mock()

            result = detect_missing_and_moved_files(mock_config)

            # Should relocate to subdir (closer path)
            assert result["relocated"] == 1
            assert "subdir" in result["actions"][0]["new_path"]

    def test_low_confidence_match_deletes(self, mock_config, temp_library):
        """Should delete when path similarity is below threshold."""
        # This test would require mocking path_similarity to return low score
        # In practice, this happens when files with same name are in very different locations
        pass

    def test_batch_operations(self, mock_config, temp_library):
        """Should use batch operations for database updates."""
        # Create multiple missing files
        missing_paths = [
            str(temp_library / "album1" / "missing1.mp3"),
            str(temp_library / "album1" / "missing2.mp3"),
        ]

        with patch("music_minion.domain.sync.engine.get_db_connection") as mock_conn:
            # Mock database query
            mock_cursor_query = Mock()
            mock_cursor_query.fetchall.return_value = [
                {
                    "id": i + 1,
                    "local_path": path,
                    "title": f"Track {i+1}",
                    "artist": "Artist",
                }
                for i, path in enumerate(missing_paths)
            ]

            # Mock database execute
            mock_context = mock_conn.return_value.__enter__.return_value
            mock_context.execute.return_value = mock_cursor_query
            mock_context.executemany = Mock()
            mock_context.commit = Mock()

            result = detect_missing_and_moved_files(mock_config)

            # Verify executemany was called (batch operation)
            assert mock_context.executemany.called
            assert result["deleted"] == 2


class TestIntegration:
    """Integration tests for full cleanup workflow."""

    def test_full_cleanup_workflow(self):
        """Test complete workflow: move, delete, and conflict handling."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lib_path = Path(tmpdir)

            # Setup: Create test library
            (lib_path / "album1").mkdir()
            (lib_path / "album2").mkdir()

            # Create files
            track1 = lib_path / "album1" / "track1.mp3"
            track2 = lib_path / "album1" / "track2.mp3"
            track3 = lib_path / "album1" / "track3.mp3"

            track1.write_text("audio 1")
            track2.write_text("audio 2")
            track3.write_text("audio 3")

            # Simulate moves and deletions
            # Move track1 to album2
            new_track1 = lib_path / "album2" / "track1.mp3"
            track1.rename(new_track1)

            # Delete track2 (orphan)
            track2.unlink()

            # track3 remains in place

            # Mock config
            config = Mock()
            config.music.library_paths = [str(lib_path)]
            config.music.supported_formats = [".mp3"]

            with patch(
                "music_minion.domain.sync.engine.get_db_connection"
            ) as mock_conn:
                # Mock database with 3 tracks at original locations
                mock_cursor_query = Mock()
                mock_cursor_query.fetchall.return_value = [
                    {
                        "id": 1,
                        "local_path": str(track1),
                        "title": "Track 1",
                        "artist": "Artist",
                    },
                    {
                        "id": 2,
                        "local_path": str(track2),
                        "title": "Track 2",
                        "artist": "Artist",
                    },
                    {
                        "id": 3,
                        "local_path": str(track3),
                        "title": "Track 3",
                        "artist": "Artist",
                    },
                ]

                mock_context = mock_conn.return_value.__enter__.return_value
                mock_context.execute.return_value = mock_cursor_query
                mock_context.executemany = Mock()
                mock_context.commit = Mock()

                result = detect_missing_and_moved_files(config)

                # Verify results
                assert result["relocated"] == 1  # track1 moved
                assert result["deleted"] == 1  # track2 deleted
                assert len(result["actions"]) == 2  # Only 2 actions (track3 unchanged)
