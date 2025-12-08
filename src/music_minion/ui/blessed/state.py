"""UI state management - immutable state updates."""

from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime
from time import time
from typing import Any, Optional

from music_minion.domain.rating.database import (
    RatingCoverageFilters,
    RatingCoverageStats,
)
from music_minion.ui.blessed.helpers.scrolling import (
    calculate_scroll_offset,
    move_selection,
)

# Maximum number of commands to keep in history
MAX_COMMAND_HISTORY = 1000


@dataclass
class TrackMetadata:
    """Track metadata from file."""

    title: str = "Unknown"
    artist: str = "Unknown"
    remix_artist: Optional[str] = None
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
class InternalCommand:
    """Type-safe internal command protocol for UI -> command handler communication."""

    action: str  # Command action type
    data: dict[str, Any] = field(default_factory=dict)  # Command data


@dataclass
class PlaylistInfo:
    """Active playlist information."""

    id: Optional[int] = None
    name: Optional[str] = None
    type: str = "manual"
    track_count: int = 0
    current_position: Optional[int] = None


@dataclass
class ScanProgress:
    """Library scan progress information."""

    is_scanning: bool = False
    files_scanned: int = 0
    total_files: int = 0
    current_file: str = ""
    phase: str = "scanning"  # 'scanning' or 'database'


@dataclass
class BuilderFilter:
    """A single filter rule for the playlist builder."""

    field: str  # title, artist, year, album, genre, bpm
    operator: (
        str  # contains, equals, gt, lt, gte, lte, not_equals, starts_with, ends_with
    )
    value: str


@dataclass
class ComparisonState:
    """Immutable comparison session state."""

    active: bool = False
    loading: bool = False  # True while loading tracks in background
    track_a: Optional[dict[str, Any]] = None
    track_b: Optional[dict[str, Any]] = None
    highlighted: str = "a"  # "a" or "b" - which track is selected
    session_id: str = ""
    comparisons_done: int = 0
    target_comparisons: int = 15
    playlist_id: Optional[int] = None
    genre_filter: Optional[str] = None
    year_filter: Optional[int] = None
    source_filter: Optional[str] = None  # 'local', 'spotify', 'soundcloud', etc.
    session_start: Optional[datetime] = None
    saved_player_state: Optional[Any] = None  # PlayerState saved before session
    filtered_tracks: list[dict[str, Any]] = field(
        default_factory=list
    )  # Tracks for session
    ratings_cache: Optional[dict[int, dict[str, Any]]] = (
        None  # Cache of {track_id: {rating, comparison_count}}
    )
    coverage_library_stats: Optional[RatingCoverageStats] = None
    coverage_filter_stats: Optional[RatingCoverageStats] = None
    coverage_library_filters: Optional[RatingCoverageFilters] = None
    coverage_filter_filters: Optional[RatingCoverageFilters] = None
    last_autoplay_track_id: Optional[int] = None
    last_autoplay_time: Optional[float] = None


@dataclass
class PlaylistBuilderState:
    """State for the playlist builder mode."""

    active: bool = False
    target_playlist_id: Optional[int] = None
    target_playlist_name: str = ""

    # Track data
    all_tracks: list[dict[str, Any]] = field(default_factory=list)
    displayed_tracks: list[dict[str, Any]] = field(default_factory=list)
    playlist_track_ids: set[int] = field(default_factory=set)

    # Selection and scroll
    selected_index: int = 0
    scroll_offset: int = 0

    # Sort/filter state
    sort_field: str = "artist"
    sort_direction: str = "asc"  # 'asc' or 'desc'
    filters: list[BuilderFilter] = field(default_factory=list)

    # Dropdown state machine: None -> 'sort' | 'filter_field' -> 'filter_operator' -> 'filter_value'
    dropdown_mode: Optional[str] = None
    dropdown_selected: int = 0
    dropdown_options: list[str] = field(default_factory=list)

    # Inline filter editor state
    filter_editor_mode: bool = False  # True when editing filters inline
    filter_editor_selected: int = 0  # Selected filter index (-1 for "add new")
    filter_editor_editing: bool = False  # True when editing a specific filter
    filter_editor_field: Optional[str] = None
    filter_editor_operator: Optional[str] = None
    filter_editor_value: str = ""
    filter_editor_step: int = 0  # 0=select field, 1=select operator, 2=enter value
    filter_editor_options: list[str] = field(
        default_factory=list
    )  # Available options for current step
    filter_editor_is_adding_new: bool = (
        False  # True when adding new filter, False when editing
    )


@dataclass
class UIState:
    """
    UI-specific state - immutable updates only.

    All state transformations return new UIState instances.
    Application state (config, tracks, player) is in AppContext, not here.
    """

    # ============================================================================
    # DASHBOARD CACHE & DISPLAY
    # ============================================================================
    # UI-derived dashboard cache (queried from DB/files for display)
    track_metadata: Optional[TrackMetadata] = None
    track_db_info: Optional[TrackDBInfo] = None
    playlist_info: PlaylistInfo = field(default_factory=PlaylistInfo)
    shuffle_enabled: bool = True  # Cached from database for display
    active_library: str = "local"  # Cached from database for display
    current_track_has_soundcloud_like: bool = False  # Cached for heart indicator

    # ============================================================================
    # COMMAND INPUT & HISTORY
    # ============================================================================
    # Command history display
    history: list[tuple[str, str]] = field(default_factory=list)  # (text, color)
    history_scroll: int = 0

    # Input field state
    input_text: str = ""
    cursor_pos: int = 0

    # Command history navigation (shell-like up/down arrow)
    command_history: list[str] = field(default_factory=list)  # Executed commands
    history_index: int | None = None  # Current position in history (None = at prompt)
    history_temp_input: str = ""  # Saved input when browsing history

    # ============================================================================
    # COMMAND PALETTE
    # ============================================================================
    # Command palette state
    palette_visible: bool = False
    palette_mode: str = "command"  # 'command', 'playlist', or 'search'
    palette_query: str = ""
    palette_items: list[tuple[str, str, str, str]] = field(
        default_factory=list
    )  # (cat, cmd, icon, desc)
    palette_selected: int = 0
    palette_scroll: int = 0

    # ============================================================================
    # CONFIRMATION DIALOG
    # ============================================================================
    # Confirmation dialog state
    confirmation_active: bool = False
    confirmation_type: Optional[str] = None  # 'delete_playlist', etc.
    confirmation_data: Optional[dict[str, Any]] = field(
        default=None
    )  # Data for confirmation action

    # ============================================================================
    # WIZARD (MULTI-STEP FLOWS)
    # ============================================================================
    # Wizard state (for multi-step wizards like smart playlist creation)
    wizard_active: bool = False
    wizard_type: Optional[str] = None  # 'smart_playlist', etc.
    wizard_step: str = (
        "field"  # Current step: 'field', 'operator', 'value', 'conjunction', 'preview'
    )
    wizard_data: dict[str, Any] = field(default_factory=dict)  # Wizard working data
    wizard_error: Optional[str] = None  # Error message for validation feedback
    wizard_selected: int = 0  # Selected option index (for arrow key navigation)
    wizard_options: list[str] = field(
        default_factory=list
    )  # Available options for current step

    # ============================================================================
    # TRACK VIEWER MODAL
    # ============================================================================
    # Track viewer state (for viewing and interacting with playlist tracks)
    track_viewer_visible: bool = False
    track_viewer_playlist_id: Optional[int] = None
    track_viewer_playlist_name: str = ""
    track_viewer_playlist_type: str = "manual"
    track_viewer_tracks: list[dict[str, Any]] = field(
        default_factory=list
    )  # All tracks
    track_viewer_filtered_tracks: list[dict[str, Any]] = field(
        default_factory=list
    )  # Filtered tracks
    track_viewer_filter_query: str = ""  # Current filter query
    track_viewer_selected: int = 0
    track_viewer_scroll: int = 0
    track_viewer_mode: str = "list"  # 'list' | 'detail' (2-mode flow like search)
    track_viewer_action_selected: int = 0  # Selected action in detail mode action menu

    # ============================================================================
    # ANALYTICS VIEWER MODAL
    # ============================================================================
    # Analytics viewer state (for viewing playlist analytics in full screen)
    analytics_viewer_visible: bool = False
    analytics_viewer_data: dict[str, Any] = field(
        default_factory=dict
    )  # Analytics data
    analytics_viewer_scroll: int = 0  # Scroll offset in lines
    analytics_viewer_total_lines: int = 0  # Total formatted lines (pre-calculated)

    # ============================================================================
    # METADATA EDITOR MODAL
    # ============================================================================
    # Metadata editor state (for editing track metadata interactively)
    editor_visible: bool = False
    editor_mode: str = "main"  # 'main' | 'list_editor' | 'editing_field'
    editor_data: dict[str, Any] = field(
        default_factory=dict
    )  # All editor state in one dict
    editor_selected: int = 0  # Selected field/item index
    editor_scroll: int = 0  # Scroll offset
    editor_changes: dict[str, Any] = field(default_factory=dict)  # Pending changes
    editor_input: str = ""  # Text input for field editing

    # ============================================================================
    # TRACK SEARCH (PALETTE MODE)
    # ============================================================================
    # Track search state (for searching and browsing all tracks in palette mode)
    search_query: str = ""
    search_all_tracks: list[dict[str, Any]] = field(
        default_factory=list
    )  # Pre-loaded once
    search_filtered_tracks: list[dict[str, Any]] = field(
        default_factory=list
    )  # Filtered results
    search_selected: int = 0  # Selected track index in filtered results
    search_scroll: int = 0  # Scroll offset for results list
    search_mode: str = (
        "search"  # Current mode: 'search' | 'detail' (actions integrated in detail)
    )
    search_detail_scroll: int = 0  # Scroll offset in detail view
    search_detail_selection: int = 0  # Selected item in detail view (action index: 0-3)

    # ============================================================================
    # AI REVIEW MODE
    # ============================================================================
    # AI Review mode state (conversational tag review)
    review_mode: Optional[str] = None  # None, 'conversation', 'confirm'
    review_data: dict[str, Any] = field(
        default_factory=dict
    )  # Track, tags, conversation history

    # ============================================================================
    # LIBRARY SCAN PROGRESS
    # ============================================================================
    # Library scan progress
    scan_progress: ScanProgress = field(default_factory=ScanProgress)

    # ============================================================================
    # COMPARISON MODE (ELO RATING)
    # ============================================================================
    # Comparison mode state (for Elo-style track comparisons)
    comparison: ComparisonState = field(default_factory=ComparisonState)

    # ============================================================================
    # PLAYLIST BUILDER MODE
    # ============================================================================
    # Playlist builder mode state (for building playlists with sort/filter)
    builder: PlaylistBuilderState = field(default_factory=PlaylistBuilderState)

    # ============================================================================
    # RATING HISTORY VIEWER MODAL
    # ============================================================================
    # Rating history viewer state (for reviewing and deleting ratings)
    rating_history_visible: bool = False
    rating_history_ratings: list[dict[str, Any]] = field(
        default_factory=list
    )  # All ratings
    rating_history_selected: int = 0  # Selected rating index
    rating_history_scroll: int = 0  # Scroll offset

    # ============================================================================
    # COMPARISON HISTORY VIEWER MODAL
    # ============================================================================
    # Comparison history viewer state (for reviewing Elo comparison decisions)
    comparison_history_visible: bool = False
    comparison_history_comparisons: list[dict[str, Any]] = field(
        default_factory=list
    )  # All comparisons
    comparison_history_selected: int = 0  # Selected comparison index
    comparison_history_scroll: int = 0  # Scroll offset

    # ============================================================================
    # UI FEEDBACK (TOAST)
    # ============================================================================
    # UI feedback (toast notifications)
    feedback_message: Optional[str] = None
    feedback_time: Optional[float] = None


def create_initial_state() -> UIState:
    """Create the initial UI state."""
    return UIState()


def update_track_info(state: UIState, track_data: dict[str, Any]) -> UIState:
    """Update track metadata and DB info."""
    metadata = TrackMetadata(
        title=track_data.get("title", "Unknown"),
        artist=track_data.get("artist", "Unknown"),
        remix_artist=track_data.get("remix_artist"),
        album=track_data.get("album"),
        year=track_data.get("year"),
        genre=track_data.get("genre"),
        bpm=track_data.get("bpm"),
        key=track_data.get("key"),
    )

    db_info = TrackDBInfo(
        tags=track_data.get("tags", []),
        notes=track_data.get("notes", ""),
        rating=track_data.get("rating"),
        last_played=track_data.get("last_played"),
        play_count=track_data.get("play_count", 0),
    )

    return replace(state, track_metadata=metadata, track_db_info=db_info)


def add_history_line(state: UIState, text: str, color: str = "white") -> UIState:
    """Add a line to command history and reset scroll to bottom."""
    # Use deque for automatic eviction, convert to list for state
    temp = deque(state.history, maxlen=MAX_COMMAND_HISTORY)
    temp.append((text, color))
    # Reset scroll to bottom when new content added
    return replace(state, history=list(temp), history_scroll=0)


def clear_history(state: UIState) -> UIState:
    """Clear command history."""
    return replace(state, history=[], history_scroll=0)


def scroll_history_up(state: UIState, lines: int = 10) -> UIState:
    """
    Scroll command history up (toward older messages).

    Args:
        state: Current UI state
        lines: Number of lines to scroll (default: 10)

    Returns:
        Updated state with new scroll position
    """
    if not state.history:
        return state

    # Increase scroll offset (moving toward older messages)
    new_scroll = min(state.history_scroll + lines, len(state.history) - 1)
    return replace(state, history_scroll=new_scroll)


def scroll_history_down(state: UIState, lines: int = 10) -> UIState:
    """
    Scroll command history down (toward newer messages).

    Args:
        state: Current UI state
        lines: Number of lines to scroll (default: 10)

    Returns:
        Updated state with new scroll position
    """
    if not state.history:
        return state

    # Decrease scroll offset (moving toward newer messages)
    new_scroll = max(state.history_scroll - lines, 0)
    return replace(state, history_scroll=new_scroll)


def scroll_history_to_top(state: UIState) -> UIState:
    """Scroll command history to the top (oldest messages)."""
    if not state.history:
        return state

    return replace(state, history_scroll=len(state.history) - 1)


def scroll_history_to_bottom(state: UIState) -> UIState:
    """Scroll command history to the bottom (newest messages)."""
    return replace(state, history_scroll=0)


def set_input_text(state: UIState, text: str) -> UIState:
    """Set input text and update cursor position."""
    return replace(state, input_text=text, cursor_pos=len(text))


def append_input_char(state: UIState, char: str) -> UIState:
    """Append character to input text."""
    new_text = state.input_text + char
    return replace(state, input_text=new_text, cursor_pos=len(new_text))


def delete_input_char(state: UIState) -> UIState:
    """Delete last character from input text (backspace)."""
    if not state.input_text:
        return state
    new_text = state.input_text[:-1]
    return replace(state, input_text=new_text, cursor_pos=len(new_text))


def toggle_palette(state: UIState) -> UIState:
    """Toggle command palette visibility."""
    return replace(state, palette_visible=not state.palette_visible)


def show_palette(state: UIState) -> UIState:
    """Show command palette."""
    return replace(state, palette_visible=True)


def hide_palette(state: UIState) -> UIState:
    """Hide palette and reset selection (including search mode state)."""
    return replace(
        state,
        palette_visible=False,
        palette_mode="command",
        palette_selected=0,
        palette_scroll=0,
        palette_query="",
        # Reset search state if in search mode
        search_query="",
        search_filtered_tracks=[],
        search_selected=0,
        search_scroll=0,
        search_mode="search",
        search_detail_scroll=0,
        search_detail_selection=0,
    )


def show_playlist_palette(
    state: UIState, items: list[tuple[str, str, str, str]]
) -> UIState:
    """Show playlist palette with items."""
    return replace(
        state,
        palette_visible=True,
        palette_mode="playlist",
        palette_items=items,
        palette_selected=0,
        palette_scroll=0,
        palette_query="",
    )


def show_device_palette(
    state: UIState, device_items: list[tuple[str, str, str, str]], device_count: int
) -> UIState:
    """Show device palette with Spotify devices.

    Args:
        state: Current UI state
        device_items: List of device items as (display_name, description, command, device_id)
        device_count: Number of devices found

    Returns:
        Updated state with palette in device mode
    """
    return replace(
        state,
        palette_visible=True,
        palette_mode="device",
        palette_items=device_items,
        palette_selected=0,
        palette_scroll=0,
        palette_query="",
    )


def show_rankings_palette(
    state: UIState,
    items: list[tuple[str, str, str, str]],
    title: str = "Top Rated Tracks",
) -> UIState:
    """Show rankings palette with top-rated tracks.

    Args:
        state: Current UI state
        items: List of ranking items as (rank, artist_title, rating_icon, rating_info)
        title: Title to display in header

    Returns:
        Updated state with palette in rankings mode
    """
    return replace(
        state,
        palette_visible=True,
        palette_mode="rankings",
        palette_items=items,
        palette_selected=0,
        palette_scroll=0,
        palette_query=title,  # Store title in query field for display
    )


def enable_palette_search_mode(
    state: UIState, all_tracks: list[dict[str, Any]]
) -> UIState:
    """
    Transform palette into track search mode.

    Args:
        state: Current UI state
        all_tracks: Pre-loaded tracks from database

    Returns:
        Updated state with palette in search mode, tracks loaded
    """
    return replace(
        state,
        palette_visible=True,
        palette_mode="search",
        palette_selected=0,
        palette_scroll=0,
        palette_query="",
        # Initialize search state - show all tracks initially
        search_query="",
        search_all_tracks=all_tracks,
        search_filtered_tracks=all_tracks,  # Show all tracks initially
        search_selected=0,
        search_scroll=0,
    )


def update_palette_filter(
    state: UIState, query: str, items: list[tuple[str, str, str, str]]
) -> UIState:
    """Update palette filter query and filtered items."""
    return replace(
        state,
        palette_query=query,
        palette_items=items,
        palette_selected=0,
        palette_scroll=0,
    )


def move_palette_selection(
    state: UIState, delta: int, visible_items: int = 10
) -> UIState:
    """
    Move palette selection up or down with scroll adjustment.

    Args:
        state: Current UI state
        delta: Direction and amount to move (-1 for up, 1 for down)
        visible_items: Number of items visible in viewport
    """
    if not state.palette_items:
        return state

    new_selected = move_selection(
        state.palette_selected, delta, len(state.palette_items)
    )
    new_scroll = calculate_scroll_offset(
        new_selected, state.palette_scroll, visible_items, len(state.palette_items)
    )

    return replace(state, palette_selected=new_selected, palette_scroll=new_scroll)


def show_confirmation(state: UIState, conf_type: str, data: dict[str, Any]) -> UIState:
    """Show confirmation dialog."""
    return replace(
        state,
        confirmation_active=True,
        confirmation_type=conf_type,
        confirmation_data=data,
    )


def hide_confirmation(state: UIState) -> UIState:
    """Hide confirmation dialog."""
    return replace(
        state, confirmation_active=False, confirmation_type=None, confirmation_data=None
    )


def set_feedback(state: UIState, message: str, icon: Optional[str] = None) -> UIState:
    """Set feedback message with optional icon."""
    msg = f"{icon} {message}" if icon else message
    return replace(state, feedback_message=msg, feedback_time=time())


def clear_feedback(state: UIState) -> UIState:
    """Clear feedback message."""
    return replace(state, feedback_message=None, feedback_time=None)


def should_show_feedback(state: UIState) -> bool:
    """Check if feedback should still be displayed (4 second window)."""
    if not state.feedback_message or not state.feedback_time:
        return False
    return (time() - state.feedback_time) < 4.0


def add_command_to_history(state: UIState, command: str) -> UIState:
    """
    Add command to history and reset navigation.

    Args:
        state: Current UI state
        command: Command to add to history

    Returns:
        Updated state with command added
    """
    # Don't add duplicate consecutive commands
    if state.command_history and state.command_history[-1] == command:
        return replace(state, history_index=None, history_temp_input="")

    # Use deque for automatic eviction, convert to list for state
    temp = deque(state.command_history, maxlen=MAX_COMMAND_HISTORY)
    temp.append(command)

    return replace(
        state, command_history=list(temp), history_index=None, history_temp_input=""
    )


def navigate_history_up(state: UIState) -> UIState:
    """
    Navigate to older command in history (up arrow).

    Args:
        state: Current UI state

    Returns:
        Updated state with older command loaded
    """
    if not state.command_history:
        return state

    # If not browsing history yet, save current input
    if state.history_index is None:
        new_index = len(state.command_history) - 1
        new_temp_input = state.input_text
        new_text = state.command_history[new_index]
    else:
        # Already browsing, move to older command
        if state.history_index > 0:
            new_index = state.history_index - 1
            new_text = state.command_history[new_index]
            new_temp_input = state.history_temp_input
        else:
            # Already at oldest command
            return state

    return replace(
        state,
        input_text=new_text,
        cursor_pos=len(new_text),
        history_index=new_index,
        history_temp_input=new_temp_input,
    )


def navigate_history_down(state: UIState) -> UIState:
    """
    Navigate to newer command in history (down arrow).

    Args:
        state: Current UI state

    Returns:
        Updated state with newer command loaded
    """
    if state.history_index is None:
        # Not browsing history
        return state

    if state.history_index < len(state.command_history) - 1:
        # Move to newer command
        new_index = state.history_index + 1
        new_text = state.command_history[new_index]
        return replace(
            state,
            input_text=new_text,
            cursor_pos=len(new_text),
            history_index=new_index,
        )
    else:
        # Reached newest command, restore saved input
        return replace(
            state,
            input_text=state.history_temp_input,
            cursor_pos=len(state.history_temp_input),
            history_index=None,
            history_temp_input="",
        )


def reset_history_navigation(state: UIState) -> UIState:
    """
    Reset history navigation state (after command execution or typing).

    Args:
        state: Current UI state

    Returns:
        Updated state with history navigation reset
    """
    return replace(state, history_index=None, history_temp_input="")


def start_wizard(
    state: UIState, wizard_type: str, initial_data: dict[str, Any]
) -> UIState:
    """
    Start a wizard flow.

    Args:
        state: Current UI state
        wizard_type: Type of wizard ('smart_playlist', etc.)
        initial_data: Initial wizard data

    Returns:
        Updated state with wizard active
    """
    # For smart_playlist, start with field options
    from ...domain.playlists import filters as playlist_filters

    initial_options = sorted(list(playlist_filters.VALID_FIELDS))

    return replace(
        state,
        wizard_active=True,
        wizard_type=wizard_type,
        wizard_step="field",
        wizard_data=initial_data,
        wizard_options=initial_options,
        wizard_selected=0,
        # Close all other modals
        palette_visible=False,
        track_viewer_visible=False,
        analytics_viewer_visible=False,
        editor_visible=False,
        confirmation_active=False,
        input_text="",
        cursor_pos=0,
    )


def update_wizard_step(
    state: UIState, step: str, options: list[str] | None = None
) -> UIState:
    """
    Update wizard to a new step.

    Args:
        state: Current UI state
        step: New step name
        options: Available options for this step (None = value entry step)

    Returns:
        Updated state
    """
    return replace(
        state,
        wizard_step=step,
        input_text="",
        cursor_pos=0,
        wizard_error=None,
        wizard_selected=0,
        wizard_options=options or [],
    )


def update_wizard_data(state: UIState, data: dict[str, Any]) -> UIState:
    """
    Update wizard data (merge with existing).

    Args:
        state: Current UI state
        data: Data to merge into wizard_data

    Returns:
        Updated state
    """
    new_data = {**state.wizard_data, **data}
    return replace(state, wizard_data=new_data)


def set_wizard_error(state: UIState, error: str) -> UIState:
    """
    Set wizard validation error message.

    Args:
        state: Current UI state
        error: Error message to display

    Returns:
        Updated state with error
    """
    return replace(state, wizard_error=error)


def clear_wizard_error(state: UIState) -> UIState:
    """
    Clear wizard validation error message.

    Args:
        state: Current UI state

    Returns:
        Updated state with error cleared
    """
    return replace(state, wizard_error=None)


def move_wizard_selection(state: UIState, delta: int) -> UIState:
    """
    Move wizard selection up or down.

    Args:
        state: Current UI state
        delta: Direction to move (-1 for up, 1 for down)

    Returns:
        Updated state with new selection
    """
    if not state.wizard_options:
        return state

    new_selected = (state.wizard_selected + delta) % len(state.wizard_options)
    return replace(state, wizard_selected=new_selected)


def cancel_wizard(state: UIState) -> UIState:
    """
    Cancel and exit wizard.

    Args:
        state: Current UI state

    Returns:
        Updated state with wizard deactivated
    """
    return replace(
        state,
        wizard_active=False,
        wizard_type=None,
        wizard_step="field",
        wizard_data={},
        wizard_error=None,
        wizard_selected=0,
        wizard_options=[],
        input_text="",
        cursor_pos=0,
    )


def show_track_viewer(
    state: UIState,
    playlist_id: int,
    playlist_name: str,
    playlist_type: str,
    tracks: list[dict[str, Any]],
) -> UIState:
    """
    Show track viewer with playlist tracks.

    Args:
        state: Current UI state
        playlist_id: ID of playlist to view
        playlist_name: Name of playlist
        playlist_type: Type of playlist ('manual' or 'smart')
        tracks: List of track dictionaries

    Returns:
        Updated state with track viewer visible
    """
    return replace(
        state,
        track_viewer_visible=True,
        track_viewer_playlist_id=playlist_id,
        track_viewer_playlist_name=playlist_name,
        track_viewer_playlist_type=playlist_type,
        track_viewer_tracks=tracks,
        track_viewer_filtered_tracks=tracks,  # Initially show all tracks
        track_viewer_filter_query="",  # No filter initially
        track_viewer_selected=0,
        track_viewer_scroll=0,
        # Close all other modals
        palette_visible=False,
        wizard_active=False,
        analytics_viewer_visible=False,
        editor_visible=False,
        confirmation_active=False,
        input_text="",
        cursor_pos=0,
    )


def hide_track_viewer(state: UIState) -> UIState:
    """
    Hide track viewer and reset state.

    Args:
        state: Current UI state

    Returns:
        Updated state with track viewer hidden
    """
    return replace(
        state,
        track_viewer_visible=False,
        track_viewer_playlist_id=None,
        track_viewer_playlist_name="",
        track_viewer_playlist_type="manual",
        track_viewer_tracks=[],
        track_viewer_filtered_tracks=[],
        track_viewer_filter_query="",
        track_viewer_selected=0,
        track_viewer_scroll=0,
        track_viewer_mode="list",
        track_viewer_action_selected=0,
    )


def move_track_viewer_selection(
    state: UIState, delta: int, visible_items: int = 10
) -> UIState:
    """
    Move track viewer selection up or down with scroll adjustment.

    Args:
        state: Current UI state
        delta: Direction and amount to move (-1 for up, 1 for down)
        visible_items: Number of items visible in viewport

    Returns:
        Updated state with new selection and scroll position
    """
    if not state.track_viewer_filtered_tracks:
        return state

    new_selected = move_selection(
        state.track_viewer_selected, delta, len(state.track_viewer_filtered_tracks)
    )
    new_scroll = calculate_scroll_offset(
        new_selected,
        state.track_viewer_scroll,
        visible_items,
        len(state.track_viewer_filtered_tracks),
    )

    return replace(
        state, track_viewer_selected=new_selected, track_viewer_scroll=new_scroll
    )


def set_track_viewer_mode(state: UIState, mode: str) -> UIState:
    """
    Change track viewer mode between list and detail.

    Args:
        state: Current UI state
        mode: New mode ('list' | 'detail')

    Returns:
        Updated state with new mode, action selection reset
    """
    return replace(
        state,
        track_viewer_mode=mode,
        track_viewer_action_selected=0,  # Reset action selection when changing modes
    )


def move_track_viewer_action_selection(
    state: UIState, delta: int, action_count: int
) -> UIState:
    """
    Move action menu selection in track viewer detail mode.

    Args:
        state: Current UI state
        delta: Direction and amount (-1 up, 1 down)
        action_count: Number of actions in menu (depends on playlist type)

    Returns:
        Updated state with new action selection
    """
    if action_count == 0:
        return state

    new_selected = (state.track_viewer_action_selected + delta) % action_count
    return replace(state, track_viewer_action_selected=new_selected)


def update_track_viewer_filter(
    state: UIState, query: str, filtered_tracks: list[dict[str, Any]]
) -> UIState:
    """
    Update track viewer filter query and filtered tracks.

    Args:
        state: Current UI state
        query: New filter query
        filtered_tracks: Filtered track list

    Returns:
        Updated state with new filter, selection and scroll reset
    """
    return replace(
        state,
        track_viewer_filter_query=query,
        track_viewer_filtered_tracks=filtered_tracks,
        track_viewer_selected=0,
        track_viewer_scroll=0,
    )


def show_analytics_viewer(state: UIState, analytics_data: dict[str, Any]) -> UIState:
    """
    Show analytics viewer with data.

    Args:
        state: Current UI state
        analytics_data: Analytics data dictionary

    Returns:
        Updated state with analytics viewer visible
    """
    # Pre-calculate total line count to avoid re-formatting on every keystroke
    from blessed import Terminal

    from music_minion.ui.blessed.components.analytics_viewer import (
        format_analytics_lines,
    )

    try:
        term = Terminal()
        all_lines = format_analytics_lines(analytics_data, term)
        total_lines = len(all_lines)

        return replace(
            state,
            analytics_viewer_visible=True,
            analytics_viewer_data=analytics_data,
            analytics_viewer_scroll=0,
            analytics_viewer_total_lines=total_lines,
            # Close all other modals
            palette_visible=False,
            wizard_active=False,
            track_viewer_visible=False,
            editor_visible=False,
            confirmation_active=False,
        )
    except Exception as e:
        # On error, show error message in history instead of crashing UI
        error_msg = f"❌ Error formatting analytics: {e}"
        return add_history_line(state, error_msg, "red")


def hide_analytics_viewer(state: UIState) -> UIState:
    """
    Hide analytics viewer and reset state.

    Args:
        state: Current UI state

    Returns:
        Updated state with analytics viewer hidden
    """
    return replace(
        state,
        analytics_viewer_visible=False,
        analytics_viewer_data={},
        analytics_viewer_scroll=0,
        analytics_viewer_total_lines=0,
    )


def scroll_analytics_viewer(state: UIState, delta: int, max_scroll: int) -> UIState:
    """
    Scroll analytics viewer up or down.

    Args:
        state: Current UI state
        delta: Amount to scroll (positive = down, negative = up)
        max_scroll: Maximum scroll offset

    Returns:
        Updated state with new scroll position
    """
    new_scroll = max(0, min(state.analytics_viewer_scroll + delta, max_scroll))
    return replace(state, analytics_viewer_scroll=new_scroll)


def start_review_mode(
    state: UIState, track_data: dict[str, Any], tags_with_reasoning: dict[str, str]
) -> UIState:
    """
    Start AI review mode for tag conversation.

    Args:
        state: Current UI state
        track_data: Track information dict
        tags_with_reasoning: Dict of {tag: reasoning}

    Returns:
        Updated state with review mode active
    """
    conversation_lines = []
    conversation_lines.append(
        f"Track: {track_data.get('artist', 'Unknown')} - {track_data.get('title', 'Unknown')}"
    )
    conversation_lines.append("")
    conversation_lines.append("Initial tags:")
    for tag, reasoning in tags_with_reasoning.items():
        conversation_lines.append(f'  • {tag}: "{reasoning}"')

    review_data = {
        "track": track_data,
        "initial_tags": tags_with_reasoning,
        "conversation_lines": conversation_lines,
    }

    return replace(
        state,
        review_mode="conversation",
        review_data=review_data,
        input_text="",
        cursor_pos=0,
    )


def enter_review_confirm(state: UIState, new_tags: dict[str, str]) -> UIState:
    """
    Enter review confirmation mode (waiting for y/n).

    Args:
        state: Current UI state
        new_tags: Regenerated tags with reasoning

    Returns:
        Updated state in confirm mode
    """
    new_data = {**state.review_data, "new_tags": new_tags}
    return replace(
        state, review_mode="confirm", review_data=new_data, input_text="", cursor_pos=0
    )


def exit_review_mode(state: UIState) -> UIState:
    """
    Exit review mode and reset state.

    Args:
        state: Current UI state

    Returns:
        Updated state with review mode exited
    """
    return replace(state, review_mode=None, review_data={}, input_text="", cursor_pos=0)


def start_scan(state: UIState, total_files: int) -> UIState:
    """
    Start library scan with progress tracking.

    Args:
        state: Current UI state
        total_files: Total number of files to scan

    Returns:
        Updated state with scan started
    """
    scan_progress = ScanProgress(
        is_scanning=True,
        files_scanned=0,
        total_files=total_files,
        current_file="",
        phase="scanning",
    )
    return replace(state, scan_progress=scan_progress)


def update_scan_progress(
    state: UIState, files_scanned: int, current_file: str, phase: str = "scanning"
) -> UIState:
    """
    Update scan progress.

    Args:
        state: Current UI state
        files_scanned: Number of files scanned so far
        current_file: Current file being processed
        phase: Current phase ('scanning' or 'database')

    Returns:
        Updated state with progress
    """
    scan_progress = replace(
        state.scan_progress,
        files_scanned=files_scanned,
        current_file=current_file,
        phase=phase,
    )
    return replace(state, scan_progress=scan_progress)


def end_scan(state: UIState) -> UIState:
    """
    End library scan.

    Args:
        state: Current UI state

    Returns:
        Updated state with scan completed
    """
    return replace(state, scan_progress=ScanProgress())


def show_metadata_editor(state: UIState, track_data: dict[str, Any]) -> UIState:
    """
    Show metadata editor with track data.

    Args:
        state: Current UI state
        track_data: Track data dict with id, metadata fields, ratings, notes, tags

    Returns:
        Updated state with editor visible
    """
    return replace(
        state,
        editor_visible=True,
        editor_mode="main",
        editor_data=track_data,
        editor_selected=0,
        editor_scroll=0,
        editor_changes={},
        # Close all other modals
        palette_visible=False,
        wizard_active=False,
        track_viewer_visible=False,
        analytics_viewer_visible=False,
        confirmation_active=False,
        input_text="",
        cursor_pos=0,
    )


def hide_metadata_editor(state: UIState) -> UIState:
    """
    Hide metadata editor and reset state.

    Args:
        state: Current UI state

    Returns:
        Updated state with editor hidden
    """
    return replace(
        state,
        editor_visible=False,
        editor_mode="main",
        editor_data={},
        editor_selected=0,
        editor_scroll=0,
        editor_changes={},
    )


def move_editor_selection(state: UIState, delta: int, max_items: int) -> UIState:
    """
    Move selection in metadata editor.

    Args:
        state: Current UI state
        delta: Direction and amount to move (-1 for up, 1 for down)
        max_items: Maximum number of items

    Returns:
        Updated state with new selection
    """
    if max_items == 0:
        return state

    new_selected = (state.editor_selected + delta) % max_items
    return replace(state, editor_selected=new_selected)


def set_editor_mode(
    state: UIState, mode: str, data: dict[str, Any] | None = None
) -> UIState:
    """
    Set editor mode (main or list_editor).

    Args:
        state: Current UI state
        mode: Editor mode ('main' or 'list_editor')
        data: Optional data to merge into editor_data

    Returns:
        Updated state with new mode
    """
    if data:
        new_data = {**state.editor_data, **data}
        return replace(
            state,
            editor_mode=mode,
            editor_data=new_data,
            editor_selected=0,
            editor_scroll=0,
        )
    else:
        return replace(state, editor_mode=mode, editor_selected=0, editor_scroll=0)


def add_editor_change(state: UIState, change_type: str, change_data: Any) -> UIState:
    """
    Add a pending change to editor.

    Args:
        state: Current UI state
        change_type: Type of change (e.g., 'basic', 'delete_rating', 'add_note')
        change_data: Change data

    Returns:
        Updated state with change added
    """
    new_changes = {**state.editor_changes}

    # For basic metadata, merge into 'basic' dict
    if change_type == "basic":
        basic = new_changes.get("basic", {})
        new_changes["basic"] = {**basic, **change_data}
    else:
        # For list changes, append to list
        if change_type not in new_changes:
            new_changes[change_type] = []
        new_changes[change_type].append(change_data)

    return replace(state, editor_changes=new_changes)


def start_field_editing(state: UIState, field_name: str, current_value: Any) -> UIState:
    """
    Enter field editing mode for a single-value field.

    Args:
        state: Current UI state
        field_name: Name of field being edited
        current_value: Current value of field (will be converted to string)

    Returns:
        Updated state in editing_field mode
    """
    # Convert value to string for editing
    value_str = str(current_value) if current_value is not None else ""

    return replace(
        state,
        editor_mode="editing_field",
        editor_input=value_str,
        editor_data={
            **state.editor_data,
            "editing_field_name": field_name,
            "editing_field_original": current_value,
        },
    )


def save_field_edit(state: UIState) -> UIState:
    """
    Save edited field value and return to main editor.

    Args:
        state: Current UI state

    Returns:
        Updated state with change saved
    """
    if state.editor_mode != "editing_field":
        return state

    field_name = state.editor_data.get("editing_field_name", "")
    new_value = state.editor_input.strip()

    # Add to pending changes
    state = add_editor_change(state, "basic", {field_name: new_value})

    # Update the display data to show new value
    new_data = {**state.editor_data}
    new_data[field_name] = new_value
    # Clean up editing fields
    new_data.pop("editing_field_name", None)
    new_data.pop("editing_field_original", None)

    return replace(state, editor_mode="main", editor_data=new_data, editor_input="")


def cancel_field_edit(state: UIState) -> UIState:
    """
    Cancel field editing and return to main editor.

    Args:
        state: Current UI state

    Returns:
        Updated state with editing cancelled
    """
    if state.editor_mode != "editing_field":
        return state

    # Clean up editing fields
    new_data = {**state.editor_data}
    new_data.pop("editing_field_name", None)
    new_data.pop("editing_field_original", None)

    return replace(state, editor_mode="main", editor_data=new_data, editor_input="")


def save_add_item(state: UIState) -> UIState:
    """
    Save new item and return to list editor.

    Args:
        state: Current UI state

    Returns:
        Updated state with item added to pending changes
    """
    if state.editor_mode != "adding_item":
        return state

    item_type = state.editor_data.get("adding_item_type", "")
    new_value = state.editor_input.strip()

    if not new_value:
        # Empty input, cancel
        return cancel_add_item(state)

    # Add to pending changes based on type
    if item_type == "notes":
        state = add_editor_change(state, "add_note", {"note_text": new_value})
    elif item_type == "tags":
        state = add_editor_change(state, "add_tag", {"tag_name": new_value})

    # Clean up adding fields
    new_data = {**state.editor_data}
    new_data.pop("adding_item_type", None)

    return replace(
        state, editor_mode="list_editor", editor_data=new_data, editor_input=""
    )


def cancel_add_item(state: UIState) -> UIState:
    """
    Cancel adding item and return to list editor.

    Args:
        state: Current UI state

    Returns:
        Updated state with adding cancelled
    """
    if state.editor_mode != "adding_item":
        return state

    # Clean up adding fields
    new_data = {**state.editor_data}
    new_data.pop("adding_item_type", None)

    return replace(
        state, editor_mode="list_editor", editor_data=new_data, editor_input=""
    )


# Track search helper functions (for palette search mode)


def update_search_query(
    state: UIState, query: str, filtered: list[dict[str, Any]]
) -> UIState:
    """
    Update search query and filtered results.

    Args:
        state: Current UI state
        query: New search query
        filtered: Filtered tracks matching query

    Returns:
        Updated state with new query, filtered results,
        selection reset to 0, scroll reset
    """
    return replace(
        state,
        search_query=query,
        search_filtered_tracks=filtered,
        search_selected=0,
        search_scroll=0,
    )


def move_search_selection(
    state: UIState, delta: int, visible_items: int = 20
) -> UIState:
    """
    Move selection in search results with scroll adjustment.

    Args:
        state: Current UI state
        delta: Direction and amount (-1 up, 1 down)
        visible_items: Number of visible items in viewport

    Returns:
        Updated state with new selection and scroll position
    """
    if not state.search_filtered_tracks:
        return state

    new_selected = move_selection(
        state.search_selected, delta, len(state.search_filtered_tracks)
    )
    new_scroll = calculate_scroll_offset(
        new_selected,
        state.search_scroll,
        visible_items,
        len(state.search_filtered_tracks),
    )

    return replace(state, search_selected=new_selected, search_scroll=new_scroll)


def set_search_mode(state: UIState, mode: str) -> UIState:
    """
    Change search mode.

    Args:
        state: Current UI state
        mode: New mode ('search' | 'detail')

    Returns:
        Updated state with new mode, scroll/selection reset
    """
    return replace(
        state,
        search_mode=mode,
        search_detail_scroll=0,
        search_detail_selection=0,  # Reset selection when changing modes
    )


def move_detail_selection(state: UIState, delta: int) -> UIState:
    """
    Move selection in combined detail view (action menu with 4 actions).

    Args:
        state: Current UI state
        delta: Direction and amount (-1 up, 1 down)

    Returns:
        Updated state with new action selection
    """
    ACTION_COUNT = 4  # Play, Add to Playlist, Edit Metadata, Cancel
    new_selected = (state.search_detail_selection + delta) % ACTION_COUNT
    return replace(state, search_detail_selection=new_selected)


def scroll_search_detail(state: UIState, delta: int, max_scroll: int) -> UIState:
    """
    Scroll detail view up or down.

    Args:
        state: Current UI state
        delta: Amount to scroll (positive = down, negative = up)
        max_scroll: Maximum scroll offset

    Returns:
        Updated state with new scroll position
    """
    new_scroll = max(0, min(state.search_detail_scroll + delta, max_scroll))
    return replace(state, search_detail_scroll=new_scroll)


def show_rating_history(state: UIState, ratings: list[dict[str, Any]]) -> UIState:
    """
    Show rating history viewer with ratings.

    Args:
        state: Current UI state
        ratings: List of rating dictionaries with track info

    Returns:
        Updated state with rating history viewer visible
    """
    return replace(
        state,
        rating_history_visible=True,
        rating_history_ratings=ratings,
        rating_history_selected=0,
        rating_history_scroll=0,
        # Close all other modals
        palette_visible=False,
        wizard_active=False,
        track_viewer_visible=False,
        analytics_viewer_visible=False,
        editor_visible=False,
        confirmation_active=False,
        input_text="",
        cursor_pos=0,
    )


def hide_rating_history(state: UIState) -> UIState:
    """
    Hide rating history viewer and reset state.

    Args:
        state: Current UI state

    Returns:
        Updated state with rating history viewer hidden
    """
    return replace(
        state,
        rating_history_visible=False,
        rating_history_ratings=[],
        rating_history_selected=0,
        rating_history_scroll=0,
    )


def move_rating_history_selection(
    state: UIState, delta: int, visible_items: int = 10
) -> UIState:
    """
    Move rating history selection up or down with scroll adjustment.

    Args:
        state: Current UI state
        delta: Direction and amount to move (-1 for up, 1 for down)
        visible_items: Number of items visible in viewport

    Returns:
        Updated state with new selection and scroll position
    """
    if not state.rating_history_ratings:
        return state

    new_selected = move_selection(
        state.rating_history_selected, delta, len(state.rating_history_ratings)
    )
    new_scroll = calculate_scroll_offset(
        new_selected,
        state.rating_history_scroll,
        visible_items,
        len(state.rating_history_ratings),
    )

    return replace(
        state, rating_history_selected=new_selected, rating_history_scroll=new_scroll
    )


def delete_rating_history_item(state: UIState, index: int) -> UIState:
    """
    Delete a rating from the history list.

    Args:
        state: Current UI state
        index: Index of rating to delete

    Returns:
        Updated state with rating removed from list
    """
    if not state.rating_history_ratings or index >= len(state.rating_history_ratings):
        return state

    new_ratings = [r for i, r in enumerate(state.rating_history_ratings) if i != index]

    # Adjust selection if needed
    new_selected = state.rating_history_selected
    if new_selected >= len(new_ratings) and len(new_ratings) > 0:
        new_selected = len(new_ratings) - 1
    elif len(new_ratings) == 0:
        new_selected = 0

    # Adjust scroll if needed
    new_scroll = state.rating_history_scroll
    if new_scroll > 0 and new_selected < new_scroll:
        new_scroll = max(0, new_selected)

    return replace(
        state,
        rating_history_ratings=new_ratings,
        rating_history_selected=new_selected,
        rating_history_scroll=new_scroll,
    )


def show_comparison_history(
    state: UIState, comparisons: list[dict[str, Any]]
) -> UIState:
    """
    Show comparison history viewer with comparisons.

    Args:
        state: Current UI state
        comparisons: List of comparison dictionaries with track info

    Returns:
        Updated state with comparison history viewer visible
    """
    return replace(
        state,
        comparison_history_visible=True,
        comparison_history_comparisons=comparisons,
        comparison_history_selected=0,
        comparison_history_scroll=0,
        # Close all other modals
        palette_visible=False,
        wizard_active=False,
        track_viewer_visible=False,
        rating_history_visible=False,
        analytics_viewer_visible=False,
        editor_visible=False,
        confirmation_active=False,
        input_text="",
        cursor_pos=0,
    )


def hide_comparison_history(state: UIState) -> UIState:
    """
    Hide comparison history viewer and reset state.

    Args:
        state: Current UI state

    Returns:
        Updated state with comparison history viewer hidden
    """
    return replace(
        state,
        comparison_history_visible=False,
        comparison_history_comparisons=[],
        comparison_history_selected=0,
        comparison_history_scroll=0,
    )


def move_comparison_history_selection(
    state: UIState, delta: int, visible_items: int = 10
) -> UIState:
    """
    Move comparison history selection up or down with scroll adjustment.

    Args:
        state: Current UI state
        delta: Direction and amount to move (-1 for up, 1 for down)
        visible_items: Number of items visible in viewport

    Returns:
        Updated state with new selection and scroll position
    """
    if not state.comparison_history_comparisons:
        return state

    new_selected = move_selection(
        state.comparison_history_selected,
        delta,
        len(state.comparison_history_comparisons),
    )
    new_scroll = calculate_scroll_offset(
        new_selected,
        state.comparison_history_scroll,
        visible_items,
        len(state.comparison_history_comparisons),
    )

    return replace(
        state,
        comparison_history_selected=new_selected,
        comparison_history_scroll=new_scroll,
    )


# ============================================================================
# PLAYLIST BUILDER HELPERS
# ============================================================================

BUILDER_SORT_FIELDS = ["title", "artist", "year", "album", "genre", "bpm"]
BUILDER_TEXT_FIELDS = {"title", "artist", "album", "genre"}
BUILDER_NUMERIC_FIELDS = {"year", "bpm"}

BUILDER_TEXT_OPERATORS = [
    ("contains", "contains"),
    ("equals", "equals"),
    ("not_equals", "not equals"),
    ("starts_with", "starts with"),
    ("ends_with", "ends with"),
]

BUILDER_NUMERIC_OPERATORS = [
    ("equals", "="),
    ("gt", ">"),
    ("lt", "<"),
    ("gte", ">="),
    ("lte", "<="),
    ("not_equals", "!="),
]


def show_playlist_builder(
    state: UIState,
    playlist_id: int,
    playlist_name: str,
    all_tracks: list[dict],
    playlist_track_ids: set[int],
    saved_state: Optional[dict] = None,
) -> UIState:
    """Show playlist builder with tracks and optionally restore saved state."""
    # Parse saved filters if present
    filters = []
    if saved_state and saved_state.get("active_filters"):
        filters = [
            BuilderFilter(f["field"], f["operator"], f["value"])
            for f in saved_state["active_filters"]
        ]

    sort_field = saved_state.get("sort_field", "artist") if saved_state else "artist"
    sort_direction = saved_state.get("sort_direction", "asc") if saved_state else "asc"
    scroll_position = saved_state.get("scroll_position", 0) if saved_state else 0

    # Apply sort and filter to get displayed tracks
    displayed = _apply_builder_filters(all_tracks, filters)
    displayed = _apply_builder_sort(displayed, sort_field, sort_direction)

    # Clamp scroll position to valid range
    scroll_position = min(scroll_position, max(0, len(displayed) - 1))

    builder_state = PlaylistBuilderState(
        active=True,
        target_playlist_id=playlist_id,
        target_playlist_name=playlist_name,
        all_tracks=all_tracks,
        displayed_tracks=displayed,
        playlist_track_ids=playlist_track_ids,
        selected_index=scroll_position,
        scroll_offset=0,
        sort_field=sort_field,
        sort_direction=sort_direction,
        filters=filters,
    )

    return replace(
        state,
        builder=builder_state,
        # Close other modals
        palette_visible=False,
        track_viewer_visible=False,
        wizard_active=False,
        input_text="",
        cursor_pos=0,
    )


def hide_playlist_builder(state: UIState) -> UIState:
    """Hide playlist builder and reset state."""
    return replace(
        state,
        builder=PlaylistBuilderState(),
    )


def move_builder_selection(
    state: UIState, delta: int, visible_items: int = 20
) -> UIState:
    """Move selection up/down with scroll adjustment."""
    if not state.builder.displayed_tracks:
        return state

    total = len(state.builder.displayed_tracks)
    new_selected = max(0, min(total - 1, state.builder.selected_index + delta))

    # Adjust scroll to keep selection visible
    new_scroll = state.builder.scroll_offset
    if new_selected < new_scroll:
        new_scroll = new_selected
    elif new_selected >= new_scroll + visible_items:
        new_scroll = new_selected - visible_items + 1

    return replace(
        state,
        builder=replace(
            state.builder,
            selected_index=new_selected,
            scroll_offset=new_scroll,
        ),
    )


def toggle_builder_track(state: UIState, track_id: int) -> UIState:
    """Toggle track in/out of playlist_track_ids set (UI state only, DB update separate)."""
    new_ids = state.builder.playlist_track_ids.copy()
    if track_id in new_ids:
        new_ids.discard(track_id)
    else:
        new_ids.add(track_id)

    return replace(
        state,
        builder=replace(state.builder, playlist_track_ids=new_ids),
    )


def show_builder_sort_dropdown(state: UIState) -> UIState:
    """Open sort field dropdown."""
    return replace(
        state,
        builder=replace(
            state.builder,
            dropdown_mode="sort",
            dropdown_selected=BUILDER_SORT_FIELDS.index(state.builder.sort_field)
            if state.builder.sort_field in BUILDER_SORT_FIELDS
            else 0,
            dropdown_options=BUILDER_SORT_FIELDS,
        ),
    )


def move_builder_dropdown_selection(state: UIState, delta: int) -> UIState:
    """Move dropdown selection."""
    if not state.builder.dropdown_options:
        return state

    total = len(state.builder.dropdown_options)
    new_selected = (state.builder.dropdown_selected + delta) % total

    return replace(
        state,
        builder=replace(state.builder, dropdown_selected=new_selected),
    )


def select_builder_sort_field(state: UIState) -> UIState:
    """Select current sort field and toggle direction, close dropdown."""
    field = state.builder.dropdown_options[state.builder.dropdown_selected]
    # Toggle direction if same field, otherwise default to asc
    direction = (
        "desc"
        if field == state.builder.sort_field and state.builder.sort_direction == "asc"
        else "asc"
    )

    # Re-sort displayed tracks
    displayed = _apply_builder_sort(state.builder.displayed_tracks, field, direction)

    return replace(
        state,
        builder=replace(
            state.builder,
            sort_field=field,
            sort_direction=direction,
            displayed_tracks=displayed,
            dropdown_mode=None,
            dropdown_options=[],
            selected_index=0,
            scroll_offset=0,
        ),
    )


def remove_builder_filter(state: UIState, index: int = -1) -> UIState:
    """Remove filter at index (default: last)."""
    if not state.builder.filters:
        return state

    new_filters = state.builder.filters.copy()
    if index == -1:
        new_filters.pop()
    else:
        new_filters.pop(index)

    # Re-apply filters and sort
    displayed = _apply_builder_filters(state.builder.all_tracks, new_filters)
    displayed = _apply_builder_sort(
        displayed, state.builder.sort_field, state.builder.sort_direction
    )

    return replace(
        state,
        builder=replace(
            state.builder,
            filters=new_filters,
            displayed_tracks=displayed,
            selected_index=0,
            scroll_offset=0,
        ),
    )


def clear_builder_filters(state: UIState) -> UIState:
    """Clear all filters."""
    displayed = _apply_builder_sort(
        state.builder.all_tracks.copy(),
        state.builder.sort_field,
        state.builder.sort_direction,
    )

    return replace(
        state,
        builder=replace(
            state.builder,
            filters=[],
            displayed_tracks=displayed,
            selected_index=0,
            scroll_offset=0,
        ),
    )


def cancel_builder_dropdown(state: UIState) -> UIState:
    """Cancel dropdown and reset pending state."""
    return replace(
        state,
        builder=replace(
            state.builder,
            dropdown_mode=None,
            dropdown_selected=0,
            dropdown_options=[],
        ),
    )


def toggle_filter_editor_mode(state: UIState) -> UIState:
    """Toggle inline filter editor mode."""
    if state.builder.filter_editor_mode:
        # Exit filter editor
        return replace(
            state,
            builder=replace(
                state.builder,
                filter_editor_mode=False,
                filter_editor_selected=0,
                filter_editor_editing=False,
                filter_editor_field=None,
                filter_editor_operator=None,
                filter_editor_value="",
                filter_editor_step=0,
            ),
        )
    else:
        # Enter filter editor
        return replace(
            state,
            builder=replace(
                state.builder,
                filter_editor_mode=True,
                filter_editor_selected=0,
                filter_editor_editing=False,
                filter_editor_field=None,
                filter_editor_operator=None,
                filter_editor_value="",
                filter_editor_step=0,
            ),
        )


def move_filter_editor_selection(state: UIState, delta: int) -> UIState:
    """Move selection in filter editor."""
    max_items = len(state.builder.filters) + 1  # +1 for "add new" option
    if max_items == 0:
        return state

    new_selected = (state.builder.filter_editor_selected + delta) % max_items
    return replace(
        state,
        builder=replace(state.builder, filter_editor_selected=new_selected),
    )


def start_editing_filter(state: UIState, filter_idx: int) -> UIState:
    """Start editing existing filter with list-based selection."""
    builder = state.builder
    if filter_idx >= len(builder.filters):
        return state

    selected_filter = builder.filters[filter_idx]
    field_options = sorted(list(BUILDER_SORT_FIELDS))

    # Find index of current field in options list
    selected_field_idx = 0
    if selected_filter.field in field_options:
        selected_field_idx = field_options.index(selected_filter.field)

    return replace(
        state,
        builder=replace(
            builder,
            filter_editor_editing=True,
            filter_editor_step=0,
            filter_editor_field=selected_filter.field,
            filter_editor_operator=selected_filter.operator,
            filter_editor_value=selected_filter.value,
            filter_editor_options=field_options,
            filter_editor_selected=selected_field_idx,  # Position at current field
            filter_editor_is_adding_new=False,
        ),
    )


def start_adding_filter(state: UIState) -> UIState:
    """Start adding new filter with list-based selection."""
    field_options = sorted(list(BUILDER_SORT_FIELDS))

    return replace(
        state,
        builder=replace(
            state.builder,
            filter_editor_editing=True,
            filter_editor_step=0,
            filter_editor_field=None,
            filter_editor_operator=None,
            filter_editor_value="",
            filter_editor_options=field_options,
            filter_editor_selected=-1,
            filter_editor_is_adding_new=True,
        ),
    )


def advance_filter_editor_step(state: UIState) -> UIState:
    """Advance to next step and set appropriate options."""
    builder = state.builder
    step = builder.filter_editor_step

    if step == 0:
        # Moving from field to operator - set operator options based on field type
        selected_field = builder.filter_editor_options[builder.filter_editor_selected]

        if selected_field in BUILDER_NUMERIC_FIELDS:
            operator_options = [op[1] for op in BUILDER_NUMERIC_OPERATORS]
        else:
            operator_options = [op[1] for op in BUILDER_TEXT_OPERATORS]

        # Find current operator index (if editing existing filter)
        selected_op_idx = 0
        if (
            builder.filter_editor_operator
            and builder.filter_editor_operator in operator_options
        ):
            selected_op_idx = operator_options.index(builder.filter_editor_operator)

        return replace(
            state,
            builder=replace(
                builder,
                filter_editor_step=1,
                filter_editor_field=selected_field,
                filter_editor_options=operator_options,
                filter_editor_selected=selected_op_idx,
            ),
        )

    elif step == 1:
        # Moving from operator to value - clear options
        selected_operator = builder.filter_editor_options[
            builder.filter_editor_selected
        ]
        return replace(
            state,
            builder=replace(
                builder,
                filter_editor_step=2,
                filter_editor_operator=selected_operator,
                filter_editor_options=[],
                filter_editor_selected=0,
            ),
        )

    return state


def update_filter_editor_field(state: UIState, field: str) -> UIState:
    """Update the field being edited in filter editor."""
    return replace(
        state,
        builder=replace(state.builder, filter_editor_field=field),
    )


def update_filter_editor_operator(state: UIState, operator: str) -> UIState:
    """Update the operator being edited in filter editor."""
    return replace(
        state,
        builder=replace(state.builder, filter_editor_operator=operator),
    )


def update_filter_editor_value(state: UIState, value: str) -> UIState:
    """Update the value being edited in filter editor."""
    return replace(
        state,
        builder=replace(state.builder, filter_editor_value=value),
    )


def _validate_filter_edit(builder: PlaylistBuilderState) -> bool:
    """Validate that required fields are present for filter editing."""
    return bool(builder.filter_editor_field and builder.filter_editor_operator)


def _create_updated_filters(builder: PlaylistBuilderState) -> list[BuilderFilter]:
    """Create updated filter list based on current editor state."""
    # Validation ensures these are not None
    assert builder.filter_editor_field is not None
    assert builder.filter_editor_operator is not None

    new_filter = BuilderFilter(
        field=builder.filter_editor_field,
        operator=builder.filter_editor_operator,
        value=builder.filter_editor_value,
    )

    if builder.filter_editor_is_adding_new:
        # Adding new filter
        return builder.filters + [new_filter]
    else:
        # Editing existing filter
        if builder.filter_editor_selected >= len(builder.filters):
            return builder.filters  # Invalid index, return unchanged

        return (
            builder.filters[: builder.filter_editor_selected]
            + [new_filter]
            + builder.filters[builder.filter_editor_selected + 1 :]
        )


def _rebuild_displayed_tracks(
    builder: PlaylistBuilderState, new_filters: list[BuilderFilter]
) -> list[dict]:
    """Rebuild displayed tracks with new filters and current sort."""
    displayed = _apply_builder_filters(builder.all_tracks, new_filters)
    return _apply_builder_sort(displayed, builder.sort_field, builder.sort_direction)


def _exit_filter_editor_with_changes(
    state: UIState, new_filters: list[BuilderFilter], displayed: list[dict]
) -> UIState:
    """Exit filter editor mode with updated filters and tracks."""
    return replace(
        state,
        builder=replace(
            state.builder,
            filters=new_filters,
            displayed_tracks=displayed,
            filter_editor_mode=False,
            filter_editor_selected=0,
            filter_editor_editing=False,
            filter_editor_field=None,
            filter_editor_operator=None,
            filter_editor_value="",
            filter_editor_step=0,
            selected_index=0,
            scroll_offset=0,
        ),
    )


def save_filter_editor_changes(state: UIState) -> UIState:
    """Save changes from filter editor and exit."""
    builder = state.builder

    # Validate changes
    if not _validate_filter_edit(builder):
        return state  # Don't save invalid changes

    # Create updated filters
    new_filters = _create_updated_filters(builder)

    # Rebuild displayed tracks
    displayed = _rebuild_displayed_tracks(builder, new_filters)

    # Exit editor with changes
    return _exit_filter_editor_with_changes(state, new_filters, displayed)


def delete_filter(state: UIState, filter_index: int) -> UIState:
    """Delete a filter at the given index."""
    if filter_index < 0 or filter_index >= len(state.builder.filters):
        return state

    new_filters = (
        state.builder.filters[:filter_index] + state.builder.filters[filter_index + 1 :]
    )

    # Re-apply filters and sort
    displayed = _apply_builder_filters(state.builder.all_tracks, new_filters)
    displayed = _apply_builder_sort(
        displayed, state.builder.sort_field, state.builder.sort_direction
    )

    return replace(
        state,
        builder=replace(
            state.builder,
            filters=new_filters,
            displayed_tracks=displayed,
            selected_index=0,
            scroll_offset=0,
        ),
    )


def _apply_builder_filters(
    tracks: list[dict], filters: list[BuilderFilter]
) -> list[dict]:
    """Apply all filters (AND logic) to tracks."""
    result = tracks
    for f in filters:
        result = [t for t in result if _matches_builder_filter(t, f)]
    return result


def _matches_builder_filter(track: dict, f: BuilderFilter) -> bool:
    """Check if track matches a single filter."""
    value = track.get(f.field)
    if value is None:
        return f.operator == "not_equals"

    if f.field in BUILDER_NUMERIC_FIELDS:
        try:
            track_val = float(value)
            filter_val = float(f.value)
        except (ValueError, TypeError):
            return False

        ops = {
            "equals": track_val == filter_val,
            "not_equals": track_val != filter_val,
            "gt": track_val > filter_val,
            "lt": track_val < filter_val,
            "gte": track_val >= filter_val,
            "lte": track_val <= filter_val,
        }
        return ops.get(f.operator, False)

    # Text field
    track_str = str(value).lower()
    filter_str = f.value.lower()

    ops = {
        "contains": filter_str in track_str,
        "equals": track_str == filter_str,
        "not_equals": track_str != filter_str,
        "starts_with": track_str.startswith(filter_str),
        "ends_with": track_str.endswith(filter_str),
    }
    return ops.get(f.operator, False)


def _apply_builder_sort(tracks: list[dict], field: str, direction: str) -> list[dict]:
    """Sort tracks by field."""
    reverse = direction == "desc"

    def sort_key(t):
        val = t.get(field)
        if val is None:
            return (1, "")  # Nulls last
        if field in BUILDER_NUMERIC_FIELDS:
            try:
                return (0, float(val))
            except (ValueError, TypeError):
                return (1, "")
        return (0, str(val).lower())

    return sorted(tracks, key=sort_key, reverse=reverse)
