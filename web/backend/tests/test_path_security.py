"""Tests for path security validation utilities."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from music_minion.core.config import MusicConfig
from music_minion.core.path_security import is_path_within_library, validate_track_path


class TestIsPathWithinLibrary:
    """Test path boundary validation."""

    def test_valid_path_within_library(self):
        """Test that valid paths within library are accepted."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lib_path = Path(temp_dir) / "music"
            lib_path.mkdir()

            # Create a file within the library
            test_file = lib_path / "song.mp3"
            test_file.write_text("fake audio")

            assert is_path_within_library(test_file, [str(lib_path)])

    def test_directory_traversal_blocked(self):
        """Test that directory traversal attacks are blocked."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lib_path = Path(temp_dir) / "music"
            lib_path.mkdir()

            # Create a file outside the library
            outside_file = Path(temp_dir) / "outside.mp3"
            outside_file.write_text("fake audio")

            # Try to access it via traversal
            traversal_path = lib_path / ".." / "outside.mp3"

            assert not is_path_within_library(traversal_path, [str(lib_path)])

    def test_symlink_escape_blocked(self):
        """Test that symlinks pointing outside library are blocked."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lib_path = Path(temp_dir) / "music"
            lib_path.mkdir()

            # Create a file outside the library
            outside_file = Path(temp_dir) / "outside.mp3"
            outside_file.write_text("fake audio")

            # Create a symlink inside library pointing outside
            symlink = lib_path / "evil_link.mp3"
            symlink.symlink_to(outside_file)

            assert not is_path_within_library(symlink, [str(lib_path)])

    def test_multiple_library_paths(self):
        """Test validation with multiple library paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lib1 = Path(temp_dir) / "music1"
            lib2 = Path(temp_dir) / "music2"
            lib1.mkdir()
            lib2.mkdir()

            # File in second library
            test_file = lib2 / "song.mp3"
            test_file.write_text("fake audio")

            assert is_path_within_library(test_file, [str(lib1), str(lib2)])

    def test_nonexistent_library_path(self):
        """Test behavior with nonexistent library paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lib_path = Path(temp_dir) / "music"
            # Don't create the directory

            test_file = Path(temp_dir) / "song.mp3"
            test_file.write_text("fake audio")

            # Should return False since library path doesn't exist
            assert not is_path_within_library(test_file, [str(lib_path)])


class TestValidateTrackPath:
    """Test complete track path validation."""

    def test_valid_path_allowed(self):
        """Test that valid existing paths within library are allowed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lib_path = Path(temp_dir) / "music"
            lib_path.mkdir()

            test_file = lib_path / "song.mp3"
            test_file.write_text("fake audio")

            config = Mock(spec=MusicConfig)
            config.library_paths = [str(lib_path)]

            result = validate_track_path(test_file, config)
            assert result == test_file

    def test_nonexistent_file_rejected(self):
        """Test that nonexistent files are rejected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lib_path = Path(temp_dir) / "music"
            lib_path.mkdir()

            nonexistent_file = lib_path / "missing.mp3"

            config = Mock(spec=MusicConfig)
            config.library_paths = [str(lib_path)]

            result = validate_track_path(nonexistent_file, config)
            assert result is None

    def test_path_outside_library_rejected(self):
        """Test that paths outside library are rejected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            lib_path = Path(temp_dir) / "music"
            lib_path.mkdir()

            outside_file = Path(temp_dir) / "outside.mp3"
            outside_file.write_text("fake audio")

            config = Mock(spec=MusicConfig)
            config.library_paths = [str(lib_path)]

            result = validate_track_path(outside_file, config)
            assert result is None
