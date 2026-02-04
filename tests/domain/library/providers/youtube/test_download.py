"""Tests for YouTube download module."""

import pytest

from music_minion.domain.library.providers.youtube.download import (
    sanitize_filename,
)
from music_minion.domain.library.providers.youtube.exceptions import (
    AgeRestrictedError,
    CopyrightBlockedError,
    DuplicateVideoError,
    InsufficientSpaceError,
    InvalidYouTubeURLError,
    VideoUnavailableError,
    YouTubeError,
)


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_basic_title(self) -> None:
        """Basic title converts to snake_case."""
        result = sanitize_filename("Hello World", ".mp4")
        assert result == "hello_world.mp4"

    def test_special_characters_removed(self) -> None:
        """Special characters are replaced with underscores."""
        result = sanitize_filename("Darude - Sandstorm (Official)", ".mp4")
        # Trailing underscores are stripped, so no underscore after "official"
        assert result == "darude_sandstorm_official.mp4"

    def test_multiple_spaces_collapsed(self) -> None:
        """Multiple spaces/hyphens collapse to single underscore."""
        result = sanitize_filename("Song   Name---Here", ".mp4")
        assert result == "song_name_here.mp4"

    def test_leading_trailing_underscores_stripped(self) -> None:
        """Leading/trailing underscores are removed."""
        result = sanitize_filename("___Title___", ".mp4")
        assert result == "title.mp4"

    def test_long_title_truncated(self) -> None:
        """Titles longer than 200 chars are truncated."""
        long_title = "a" * 300
        result = sanitize_filename(long_title, ".mp4")
        # max_base_length = 200 - len(".mp4") = 196
        assert len(result) <= 200
        assert result.endswith(".mp4")

    def test_different_extension(self) -> None:
        """Works with different extensions."""
        result = sanitize_filename("My Video", ".webm")
        assert result == "my_video.webm"

    def test_unicode_characters(self) -> None:
        """Unicode characters are converted appropriately."""
        result = sanitize_filename("日本語 タイトル", ".mp4")
        # Unicode word characters are preserved in Python \w
        assert result.endswith(".mp4")
        assert "_" in result  # Space becomes underscore


class TestExceptions:
    """Tests for custom YouTube exceptions."""

    def test_youtube_error_base(self) -> None:
        """YouTubeError is the base exception."""
        with pytest.raises(YouTubeError):
            raise YouTubeError("Base error")

    def test_invalid_url_inherits(self) -> None:
        """InvalidYouTubeURLError inherits from YouTubeError."""
        with pytest.raises(YouTubeError):
            raise InvalidYouTubeURLError("Bad URL")

    def test_video_unavailable_inherits(self) -> None:
        """VideoUnavailableError inherits from YouTubeError."""
        with pytest.raises(YouTubeError):
            raise VideoUnavailableError("Gone")

    def test_age_restricted_inherits(self) -> None:
        """AgeRestrictedError inherits from YouTubeError."""
        with pytest.raises(YouTubeError):
            raise AgeRestrictedError("18+")

    def test_copyright_blocked_inherits(self) -> None:
        """CopyrightBlockedError inherits from YouTubeError."""
        with pytest.raises(YouTubeError):
            raise CopyrightBlockedError("DMCA")

    def test_insufficient_space_inherits(self) -> None:
        """InsufficientSpaceError inherits from YouTubeError."""
        with pytest.raises(YouTubeError):
            raise InsufficientSpaceError("No space")

    def test_duplicate_video_has_track_id(self) -> None:
        """DuplicateVideoError stores the track ID."""
        error = DuplicateVideoError(track_id=42)
        assert error.track_id == 42
        assert "42" in str(error)

    def test_duplicate_video_custom_message(self) -> None:
        """DuplicateVideoError accepts custom message."""
        error = DuplicateVideoError(track_id=99, message="Custom msg")
        assert error.track_id == 99
        assert str(error) == "Custom msg"
