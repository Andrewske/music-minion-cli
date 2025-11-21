"""
SpotifyPlayer - thin wrapper for Spotify Connect API.

Provides unified playback interface matching existing MusicPlayer pattern.
Implements cached polling strategy to respect API rate limits.
"""

import time
from typing import Optional

from loguru import logger

from music_minion.core.output import log

from ..library.provider import ProviderState


class SpotifyPlayer:
    """Thin wrapper for Spotify Connect API with cached polling.

    Justified exception to functional pattern because:
    - Matches existing MPVPlayer interface
    - Caches playback state (5-10s polling interval)
    - Interpolates position between polls (respects rate limits)
    - External API requires stateful session management

    Pattern: Thin class wrapper around pure API functions (in api.py).
    """

    def __init__(self, provider_state: ProviderState, device_id: Optional[str] = None):
        """Initialize Spotify player.

        Args:
            provider_state: Spotify provider state with auth tokens
            device_id: Optional specific device ID (otherwise uses active device)
        """
        self.provider_state = provider_state
        self.device_id = device_id or self._get_active_device()

        # Cached state for rate-limit-friendly polling
        self.cached_position = 0.0
        self.cached_duration = 0.0
        self.cached_is_playing = False
        self.last_poll_time = 0.0
        self.last_actual_position = 0.0
        self.last_position_time = 0.0

        logger.debug(f"Initialized SpotifyPlayer with device: {self.device_id}")

    def play(self, spotify_uri: str) -> bool:
        """Start playback via Spotify Connect.

        Args:
            spotify_uri: Spotify URI (spotify:track:{id}) or track ID

        Returns:
            True if playback started successfully
        """
        from music_minion.domain.library.providers.spotify import api

        # Extract track ID from URI if needed
        track_id = spotify_uri.split(":")[-1] if ":" in spotify_uri else spotify_uri

        if not self.device_id:
            logger.error("Cannot play - no Spotify device available")
            log("❌ No Spotify device available. Open Spotify on a device first.", level="error")
            return False

        success = api._spotify_play(self.provider_state, track_id, self.device_id)
        if success:
            logger.info(f"Playing Spotify track: {track_id}")
            self._refresh_cached_state()
        else:
            logger.error(f"Failed to play track: {track_id}")
        return success

    def pause(self) -> bool:
        """Pause Spotify playback.

        Returns:
            True if successfully paused
        """
        from music_minion.domain.library.providers.spotify import api

        success = api._spotify_pause(self.provider_state)
        if success:
            self.cached_is_playing = False
            logger.debug("Paused Spotify playback")
        return success

    def resume(self) -> bool:
        """Resume Spotify playback.

        Returns:
            True if successfully resumed
        """
        from music_minion.domain.library.providers.spotify import api

        success = api._spotify_resume(self.provider_state)
        if success:
            self.cached_is_playing = True
            self.last_position_time = time.time()
            logger.debug("Resumed Spotify playback")
        return success

    def stop(self) -> bool:
        """Stop Spotify playback (Spotify doesn't have stop, uses pause).

        Returns:
            True if successfully stopped
        """
        return self.pause()

    def seek(self, position: float) -> bool:
        """Seek to position in seconds.

        Args:
            position: Position in seconds

        Returns:
            True if successfully seeked
        """
        from music_minion.domain.library.providers.spotify import api

        position_ms = int(position * 1000)
        success = api._spotify_seek(self.provider_state, position_ms)
        if success:
            self.cached_position = position
            self.last_actual_position = position
            self.last_position_time = time.time()
            logger.debug(f"Seeked to position: {position}s")
        return success

    def get_time_pos(self) -> Optional[float]:
        """Get current playback position with cached interpolation.

        Polls Spotify API every 5 seconds to respect rate limits.
        Between polls, interpolates position if playing.

        Returns:
            Current position in seconds, or None if unavailable
        """
        from music_minion.domain.library.providers.spotify import api

        now = time.time()

        # Poll Spotify API every 5 seconds
        if now - self.last_poll_time > 5.0:
            playback = api._spotify_get_current_playback(self.provider_state)
            if playback:
                self.cached_position = playback.get("progress_ms", 0) / 1000.0
                if playback.get("item"):
                    self.cached_duration = playback["item"].get("duration_ms", 0) / 1000.0
                self.cached_is_playing = playback.get("is_playing", False)
                self.last_actual_position = self.cached_position
                self.last_position_time = now
                self.last_poll_time = now
                logger.debug(f"Polled playback state: pos={self.cached_position}s, playing={self.cached_is_playing}")
        elif self.cached_is_playing:
            # Interpolate between polls (only if playing)
            elapsed = now - self.last_position_time
            self.cached_position = self.last_actual_position + elapsed

        return self.cached_position

    def is_playing(self) -> bool:
        """Check if currently playing (uses cached state).

        Returns:
            True if playing, False otherwise
        """
        return self.cached_is_playing

    def get_duration(self) -> Optional[float]:
        """Get current track duration (uses cached state).

        Returns:
            Duration in seconds, or None if unavailable
        """
        return self.cached_duration if self.cached_duration > 0 else None

    def _get_active_device(self) -> Optional[str]:
        """Get active Spotify device or first available.

        Returns:
            Device ID or None if no devices available
        """
        from music_minion.domain.library.providers.spotify import api

        devices = api._spotify_get_devices(self.provider_state)

        # Try active device first
        for device in devices:
            if device.get("is_active"):
                logger.debug(f"Using active Spotify device: {device['name']}")
                return device["id"]

        # Fall back to first available
        if devices:
            logger.debug(f"No active device, using first available: {devices[0]['name']}")
            return devices[0]["id"]

        # No devices available
        logger.warning("No Spotify devices available")
        log("⚠ No Spotify devices found. Open Spotify on a device first.", level="warning")
        return None

    def _refresh_cached_state(self) -> None:
        """Force immediate cache refresh (e.g., after play command)."""
        self.last_poll_time = 0.0  # Force next get_time_pos() to poll
        self.get_time_pos()
