"""Application context for explicit state passing.

This module provides the AppContext dataclass that encapsulates all application state,
enabling functional programming patterns with explicit state passing instead of global
mutable state accessed via import hacks.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable

try:
    from rich.console import Console
except ImportError:
    Console = None

from music_minion.core.config import Config
from music_minion.domain.library.models import Track
from music_minion.domain.playback.player import PlayerState


@dataclass
class AppContext:
    """Immutable application context passed to all functions.

    This context encapsulates all application state and is passed explicitly
    to functions that need it. Functions return updated contexts rather than
    mutating global state.

    Attributes:
        config: Application configuration
        music_tracks: List of all music tracks in library
        player_state: Current MPV player state
        console: Rich Console for formatted output (None if Rich not available)
        ui_action: Optional UI action signal for command handlers to request UI operations
    """

    # Configuration
    config: Config

    # State
    music_tracks: List[Track]
    player_state: PlayerState

    # UI
    console: Optional[Console] = None
    provider_states: Dict[str, Any] = field(default_factory=dict)  # Provider auth states (SoundCloud, Spotify, etc.)
    ui_action: Optional[Dict[str, Any]] = field(default=None)
    ui_mode: str = 'cli'  # 'cli' or 'blessed'
    update_ui_state: Optional[Callable[[Dict[str, Any]], None]] = field(default=None)  # Thread-safe UIState updater

    @classmethod
    def create(cls, config: Config, console: Optional[Console] = None) -> 'AppContext':
        """Create initial application context.

        Args:
            config: Application configuration
            console: Optional Rich Console instance

        Returns:
            New AppContext with empty tracks and default player state
        """
        return cls(
            config=config,
            music_tracks=[],
            player_state=PlayerState(),
            provider_states={},
            console=console,
            ui_action=None,
            ui_mode='cli',
            update_ui_state=None,
        )

    def with_tracks(self, tracks: List[Track]) -> 'AppContext':
        """Return new context with updated tracks.

        Args:
            tracks: New list of tracks

        Returns:
            New AppContext with updated tracks, other fields unchanged
        """
        return AppContext(
            config=self.config,
            music_tracks=tracks,
            player_state=self.player_state,
            provider_states=self.provider_states,
            console=self.console,
            ui_action=self.ui_action,
            ui_mode=self.ui_mode,
            update_ui_state=self.update_ui_state,
        )

    def with_player_state(self, state: PlayerState) -> 'AppContext':
        """Return new context with updated player state.

        Args:
            state: New player state

        Returns:
            New AppContext with updated player state, other fields unchanged
        """
        return AppContext(
            config=self.config,
            music_tracks=self.music_tracks,
            player_state=state,
            provider_states=self.provider_states,
            console=self.console,
            ui_action=self.ui_action,
            ui_mode=self.ui_mode,
            update_ui_state=self.update_ui_state,
        )

    def with_config(self, config: Config) -> 'AppContext':
        """Return new context with updated configuration.

        Args:
            config: New configuration

        Returns:
            New AppContext with updated config, other fields unchanged
        """
        return AppContext(
            config=config,
            music_tracks=self.music_tracks,
            player_state=self.player_state,
            provider_states=self.provider_states,
            console=self.console,
            ui_action=self.ui_action,
            ui_mode=self.ui_mode,
            update_ui_state=self.update_ui_state,
        )

    def with_provider_states(self, provider_states: Dict[str, Any]) -> 'AppContext':
        """Return new context with updated provider states.

        Args:
            provider_states: New provider states dictionary

        Returns:
            New AppContext with updated provider_states, other fields unchanged
        """
        return AppContext(
            config=self.config,
            music_tracks=self.music_tracks,
            player_state=self.player_state,
            provider_states=provider_states,
            console=self.console,
            ui_action=self.ui_action,
            ui_mode=self.ui_mode,
            update_ui_state=self.update_ui_state,
        )

    def with_ui_action(self, action: Optional[Dict[str, Any]]) -> 'AppContext':
        """Return new context with UI action signal.

        Args:
            action: UI action dictionary or None to clear

        Returns:
            New AppContext with updated ui_action, other fields unchanged
        """
        return AppContext(
            config=self.config,
            music_tracks=self.music_tracks,
            player_state=self.player_state,
            provider_states=self.provider_states,
            console=self.console,
            ui_action=action,
            ui_mode=self.ui_mode,
            update_ui_state=self.update_ui_state,
        )
