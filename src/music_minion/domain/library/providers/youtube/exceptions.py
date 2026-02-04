"""YouTube-specific exceptions for error handling."""


class YouTubeError(Exception):
    """Base exception for YouTube operations."""

    pass


class InvalidYouTubeURLError(YouTubeError):
    """Raised when URL is not a valid YouTube URL."""

    pass


class VideoUnavailableError(YouTubeError):
    """Raised when video is deleted or unavailable."""

    pass


class AgeRestrictedError(YouTubeError):
    """Raised when video requires age verification."""

    pass


class CopyrightBlockedError(YouTubeError):
    """Raised when video is blocked due to copyright."""

    pass


class DuplicateVideoError(YouTubeError):
    """Raised when video is already imported."""

    def __init__(self, track_id: int, message: str = None):
        self.track_id = track_id
        super().__init__(message or f"Video already imported as track #{track_id}")


class InsufficientSpaceError(YouTubeError):
    """Raised when disk space is insufficient."""

    pass
