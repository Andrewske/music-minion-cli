"""
Centralized application state management
Following Claude Code pattern of lightweight shell with clean state
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class PlayerState:
    """Player-specific state"""
    current_track: Optional[str] = None
    is_playing: bool = False
    is_paused: bool = False
    current_position: float = 0.0
    duration: float = 0.0
    process: Any = None  # MPV process handle


@dataclass
class TrackMetadata:
    """Current track metadata"""
    title: str = "Unknown"
    artist: str = "Unknown"
    album: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    bpm: Optional[int] = None
    key: Optional[str] = None


@dataclass
class TrackDBInfo:
    """Database information for current track"""
    tags: List[str] = field(default_factory=list)
    notes: str = ""
    rating: Optional[int] = None
    last_played: Optional[str] = None
    play_count: int = 0


@dataclass
class PlaylistInfo:
    """Active playlist information"""
    id: Optional[int] = None
    name: Optional[str] = None
    type: str = "manual"  # 'manual' or 'smart'
    track_count: int = 0
    current_position: Optional[int] = None


@dataclass
class UIState:
    """UI-specific state (feedback messages, previous track, etc.)"""
    feedback_message: Optional[str] = None
    feedback_time: Optional[float] = None
    previous_track: Optional[Dict[str, Any]] = None
    previous_rating: Optional[str] = None
    previous_time: Optional[float] = None
    shuffle_enabled: bool = True

    @property
    def should_show_feedback(self) -> bool:
        """Check if feedback should still be displayed (4 second window)"""
        if not self.feedback_message or not self.feedback_time:
            return False
        from time import time
        return (time() - self.feedback_time) < 4.0


@dataclass
class AppState:
    """
    Complete application state.
    Centralizes all mutable state in one place for easier testing and debugging.
    """
    # Core states
    player: PlayerState = field(default_factory=PlayerState)
    track_metadata: Optional[TrackMetadata] = None
    track_db_info: Optional[TrackDBInfo] = None
    playlist: PlaylistInfo = field(default_factory=PlaylistInfo)
    ui: UIState = field(default_factory=UIState)

    # Library state
    music_tracks: List[Any] = field(default_factory=list)  # List of library.Track objects

    # Config
    config: Any = None  # config.Config object

    def set_feedback(self, message: str, icon: Optional[str] = None) -> None:
        """Set a feedback message to display"""
        from time import time
        if icon:
            self.ui.feedback_message = f"{icon} {message}"
        else:
            self.ui.feedback_message = message
        self.ui.feedback_time = time()

    def clear_feedback(self) -> None:
        """Clear feedback message"""
        self.ui.feedback_message = None
        self.ui.feedback_time = None

    def store_previous_track(self, track_info: Dict[str, Any], rating: str) -> None:
        """Store information about the previous track"""
        from time import time
        self.ui.previous_track = track_info.copy()
        self.ui.previous_rating = rating
        self.ui.previous_time = time()

    def get_current_track_from_library(self) -> Optional[Any]:
        """Get current track object from library"""
        if not self.player.current_track:
            return None

        for track in self.music_tracks:
            if str(track.file_path) == self.player.current_track:
                return track
        return None
