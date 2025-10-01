"""
Runner module - integrates Textual UI with existing Music Minion logic
"""

import threading
from typing import Callable, Any

from .app import MusicMinionApp
from .state import AppState


class MusicMinionRunner:
    """
    Manages the Textual app and integrates with existing Music Minion modules.
    Replaces the manual dashboard update thread with Textual's reactive system.
    """

    def __init__(self, config: Any, music_tracks: list, initial_player_state: Any):
        """
        Initialize the runner.

        Args:
            config: Music Minion config object
            music_tracks: List of library.Track objects
            initial_player_state: Initial player.PlayerState object
        """
        # Initialize centralized state
        self.app_state = AppState()
        self.app_state.config = config
        self.app_state.music_tracks = music_tracks

        # Initialize player state from existing player
        self.app_state.player.current_track = initial_player_state.current_track
        self.app_state.player.is_playing = initial_player_state.is_playing
        # Player.PlayerState doesn't have is_paused, derive it from is_playing
        self.app_state.player.is_paused = not initial_player_state.is_playing and initial_player_state.current_track is not None
        self.app_state.player.current_position = initial_player_state.current_position
        self.app_state.player.duration = initial_player_state.duration
        self.app_state.player.process = initial_player_state.process

        # Command handler will be set by caller
        self.command_handler = None

        # The Textual app instance
        self.app = None

        # Background thread for player state updates
        self.update_thread = None
        self.running = False

    def set_command_handler(self, handler: Callable[[str, list], bool]) -> None:
        """
        Set the command handler function.

        Args:
            handler: Function that takes (command: str, args: list) -> bool
                    Returns True to continue, False to exit
        """
        self.command_handler = handler

    def run(self) -> None:
        """Start the Textual app"""
        if not self.command_handler:
            raise ValueError("Command handler must be set before running")

        # Create the Textual app
        self.app = MusicMinionApp(self.app_state, self.command_handler)

        # Start background update thread
        self.running = True
        self.update_thread = threading.Thread(
            target=self._background_updater,
            daemon=True,
            name="StateUpdater"
        )
        self.update_thread.start()

        # Run the app (blocking)
        try:
            self.app.run()
        finally:
            self.running = False

    def _background_updater(self) -> None:
        """
        Background thread to update player state periodically.
        Polls the player and updates app state, which triggers Textual updates.
        """
        import time
        from .. import player, database

        while self.running:
            try:
                # Update player state if there's a process
                if self.app_state.player.process:
                    # Import the player state update function
                    updated_state = player.update_player_status(
                        self.app_state.player  # Pass the player state from our AppState
                    )

                    # Update our centralized state
                    self.app_state.player.current_track = updated_state.current_track
                    self.app_state.player.is_playing = updated_state.is_playing
                    # Derive is_paused from is_playing and whether there's a current track
                    self.app_state.player.is_paused = not updated_state.is_playing and updated_state.current_track is not None
                    self.app_state.player.current_position = updated_state.current_position
                    self.app_state.player.duration = updated_state.duration
                    self.app_state.player.process = updated_state.process

                # Update track metadata if track changed
                current_track = self.app_state.get_current_track_from_library()
                if current_track:
                    self._update_track_metadata(current_track)
                    self._update_track_db_info(current_track)

                # Update playlist info
                self._update_playlist_info()

                # Sleep for a bit
                time.sleep(0.5)

            except Exception as e:
                # Don't crash the background thread
                import traceback
                traceback.print_exc()
                time.sleep(1.0)

    def _update_track_metadata(self, track: Any) -> None:
        """Update track metadata from library track"""
        from .state import TrackMetadata

        self.app_state.track_metadata = TrackMetadata(
            title=track.title or "Unknown",
            artist=track.artist or "Unknown",
            album=track.album,
            year=track.year,
            genre=track.genre,
            bpm=track.bpm,
            key=track.key,
        )

    def _update_track_db_info(self, track: Any) -> None:
        """Update track database info"""
        from .. import database
        from .state import TrackDBInfo

        try:
            # Get track ID
            track_id = database.get_or_create_track(
                track.file_path, track.title, track.artist, track.album,
                track.genre, track.year, track.duration, track.key, track.bpm
            )

            # Get tags
            tags_data = database.get_track_tags(track_id)
            tags = [t['tag_name'] for t in tags_data if not t.get('blacklisted', False)]

            # Get ratings
            ratings = database.get_track_ratings(track_id)
            latest_rating = None
            if ratings:
                rating_map = {"archive": 0, "skip": 25, "like": 60, "love": 85}
                latest_rating = rating_map.get(ratings[0]['rating_type'], 50)

            # Get notes
            notes_data = database.get_track_notes(track_id)
            latest_note = notes_data[0]['note'] if notes_data else ""

            # Get play stats
            play_count = len(ratings)
            last_played = ratings[0]['created_at'] if ratings else None

            self.app_state.track_db_info = TrackDBInfo(
                tags=tags,
                notes=latest_note,
                rating=latest_rating,
                last_played=last_played,
                play_count=play_count,
            )

        except Exception:
            # Graceful degradation
            self.app_state.track_db_info = None

    def _update_playlist_info(self) -> None:
        """Update active playlist info"""
        from .. import playlist, playback
        from .state import PlaylistInfo

        try:
            active = playlist.get_active_playlist()
            if active:
                # Get track count
                track_count = playlist.get_playlist_track_count(active['id'])

                # Get position if in sequential mode
                current_position = None
                try:
                    shuffle_enabled = playback.get_shuffle_mode()
                    if not shuffle_enabled:
                        saved_position = playback.get_playlist_position(active['id'])
                        if saved_position:
                            _, current_position = saved_position
                except Exception:
                    pass

                self.app_state.playlist = PlaylistInfo(
                    id=active['id'],
                    name=active['name'],
                    type=active['type'],
                    track_count=track_count,
                    current_position=current_position,
                )

                # Update shuffle mode
                try:
                    shuffle_enabled = playback.get_shuffle_mode()
                    self.app_state.ui.shuffle_enabled = shuffle_enabled
                except Exception:
                    pass
            else:
                self.app_state.playlist = PlaylistInfo()

        except Exception:
            # Graceful degradation
            self.app_state.playlist = PlaylistInfo()
