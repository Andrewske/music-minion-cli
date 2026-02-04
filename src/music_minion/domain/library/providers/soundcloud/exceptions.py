"""SoundCloud-specific exceptions for error handling."""


class SoundCloudError(Exception):
    """Base exception for SoundCloud operations."""

    pass


class InvalidSoundCloudURLError(SoundCloudError):
    """Raised when URL is not a valid SoundCloud URL."""

    pass


class TrackUnavailableError(SoundCloudError):
    """Raised when track is deleted, private, or unavailable."""

    pass


class PlaylistUnavailableError(SoundCloudError):
    """Raised when playlist is deleted, private, or unavailable."""

    pass


class DuplicateTrackError(SoundCloudError):
    """Raised when track is already imported."""

    def __init__(self, track_id: int, message: str = None):
        self.track_id = track_id
        super().__init__(message or f"Track already imported as track #{track_id}")


class RateLimitedError(SoundCloudError):
    """Raised when SoundCloud rate limits the request."""

    pass


class AuthenticationError(SoundCloudError):
    """Raised when SoundCloud authentication fails."""

    pass
