"""UI state management - immutable state updates."""

from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class PlayerState:
    """Player state snapshot."""
    current_track: Optional[str] = None
    is_playing: bool = False
    is_paused: bool = False
    current_position: float = 0.0
    duration: float = 0.0
    process: Any = None


@dataclass
class TrackMetadata:
    """Track metadata from file."""
    title: str = "Unknown"
    artist: str = "Unknown"
    album: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    bpm: Optional[int] = None
    key: Optional[str] = None


@dataclass
class TrackDBInfo:
    """Track database information."""
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    rating: Optional[int] = None
    last_played: Optional[str] = None
    play_count: int = 0


@dataclass
class PlaylistInfo:
    """Active playlist information."""
    id: Optional[int] = None
    name: Optional[str] = None
    type: str = "manual"
    track_count: int = 0
    current_position: Optional[int] = None


@dataclass
class UIState:
    """
    Complete UI state - immutable updates only.

    All state transformations return new UIState instances.
    """
    # Dashboard data
    player: PlayerState = field(default_factory=PlayerState)
    track_metadata: Optional[TrackMetadata] = None
    track_db_info: Optional[TrackDBInfo] = None
    playlist_info: PlaylistInfo = field(default_factory=PlaylistInfo)

    # History
    history: list[tuple[str, str]] = field(default_factory=list)  # (text, color)
    history_scroll: int = 0

    # Input
    input_text: str = ""
    cursor_pos: int = 0

    # Palette
    palette_visible: bool = False
    palette_query: str = ""
    palette_items: list[tuple[str, str, str]] = field(default_factory=list)  # (cmd, icon, desc)
    palette_selected: int = 0

    # UI feedback
    feedback_message: Optional[str] = None
    feedback_time: Optional[float] = None

    # Shuffle state
    shuffle_enabled: bool = True

    # Library and config
    music_tracks: list[Any] = field(default_factory=list)
    config: Any = None


def create_initial_state() -> UIState:
    """Create the initial UI state."""
    return UIState()


def update_player_state(state: UIState, player_data: dict[str, Any]) -> UIState:
    """Update player state from player data."""
    from dataclasses import replace
    new_player = replace(
        state.player,
        current_track=player_data.get('current_track', state.player.current_track),
        is_playing=player_data.get('is_playing', state.player.is_playing),
        is_paused=player_data.get('is_paused', state.player.is_paused),
        current_position=player_data.get('current_position', state.player.current_position),
        duration=player_data.get('duration', state.player.duration),
    )
    return replace(state, player=new_player)


def update_track_info(state: UIState, track_data: dict[str, Any]) -> UIState:
    """Update track metadata and DB info."""
    from dataclasses import replace

    metadata = TrackMetadata(
        title=track_data.get('title', 'Unknown'),
        artist=track_data.get('artist', 'Unknown'),
        album=track_data.get('album'),
        year=track_data.get('year'),
        genre=track_data.get('genre'),
        bpm=track_data.get('bpm'),
        key=track_data.get('key'),
    )

    db_info = TrackDBInfo(
        tags=track_data.get('tags', []),
        notes=track_data.get('notes', ''),
        rating=track_data.get('rating'),
        last_played=track_data.get('last_played'),
        play_count=track_data.get('play_count', 0),
    )

    return replace(state, track_metadata=metadata, track_db_info=db_info)


def add_history_line(state: UIState, text: str, color: str = 'white') -> UIState:
    """Add a line to command history."""
    from dataclasses import replace
    new_history = state.history + [(text, color)]
    return replace(state, history=new_history)


def clear_history(state: UIState) -> UIState:
    """Clear command history."""
    from dataclasses import replace
    return replace(state, history=[])


def set_input_text(state: UIState, text: str) -> UIState:
    """Set input text and update cursor position."""
    from dataclasses import replace
    return replace(state, input_text=text, cursor_pos=len(text))


def append_input_char(state: UIState, char: str) -> UIState:
    """Append character to input text."""
    from dataclasses import replace
    new_text = state.input_text + char
    return replace(state, input_text=new_text, cursor_pos=len(new_text))


def delete_input_char(state: UIState) -> UIState:
    """Delete last character from input text (backspace)."""
    from dataclasses import replace
    if not state.input_text:
        return state
    new_text = state.input_text[:-1]
    return replace(state, input_text=new_text, cursor_pos=len(new_text))


def toggle_palette(state: UIState) -> UIState:
    """Toggle command palette visibility."""
    from dataclasses import replace
    return replace(state, palette_visible=not state.palette_visible)


def show_palette(state: UIState) -> UIState:
    """Show command palette."""
    from dataclasses import replace
    return replace(state, palette_visible=True)


def hide_palette(state: UIState) -> UIState:
    """Hide command palette and reset selection."""
    from dataclasses import replace
    return replace(state, palette_visible=False, palette_selected=0, palette_query="")


def update_palette_filter(state: UIState, query: str, items: list[tuple[str, str, str]]) -> UIState:
    """Update palette filter query and filtered items."""
    from dataclasses import replace
    return replace(state, palette_query=query, palette_items=items, palette_selected=0)


def move_palette_selection(state: UIState, delta: int) -> UIState:
    """Move palette selection up or down."""
    from dataclasses import replace
    if not state.palette_items:
        return state
    new_selected = (state.palette_selected + delta) % len(state.palette_items)
    return replace(state, palette_selected=new_selected)


def set_feedback(state: UIState, message: str, icon: Optional[str] = None) -> UIState:
    """Set feedback message with optional icon."""
    from dataclasses import replace
    from time import time
    msg = f"{icon} {message}" if icon else message
    return replace(state, feedback_message=msg, feedback_time=time())


def clear_feedback(state: UIState) -> UIState:
    """Clear feedback message."""
    from dataclasses import replace
    return replace(state, feedback_message=None, feedback_time=None)


def should_show_feedback(state: UIState) -> bool:
    """Check if feedback should still be displayed (4 second window)."""
    if not state.feedback_message or not state.feedback_time:
        return False
    from time import time
    return (time() - state.feedback_time) < 4.0
