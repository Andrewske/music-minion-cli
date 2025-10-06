"""UI state management - immutable state updates."""

from dataclasses import dataclass, field, replace
from time import time
from typing import Optional, Any

# Maximum number of commands to keep in history
MAX_COMMAND_HISTORY = 1000


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
class UIState:
    """
    UI-specific state - immutable updates only.

    All state transformations return new UIState instances.
    Application state (config, tracks, player) is in AppContext, not here.
    """
    # UI-derived dashboard cache (queried from DB/files for display)
    track_metadata: Optional[TrackMetadata] = None
    track_db_info: Optional[TrackDBInfo] = None
    playlist_info: PlaylistInfo = field(default_factory=PlaylistInfo)
    shuffle_enabled: bool = True  # Cached from database for display

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

    # Command palette state
    palette_visible: bool = False
    palette_mode: str = 'command'  # 'command' or 'playlist'
    palette_query: str = ""
    palette_items: list[tuple[str, str, str, str]] = field(default_factory=list)  # (cat, cmd, icon, desc)
    palette_selected: int = 0
    palette_scroll: int = 0

    # Confirmation dialog state
    confirmation_active: bool = False
    confirmation_type: Optional[str] = None  # 'delete_playlist', etc.
    confirmation_data: Optional[dict[str, Any]] = field(default=None)  # Data for confirmation action

    # Wizard state (for multi-step wizards like smart playlist creation)
    wizard_active: bool = False
    wizard_type: Optional[str] = None  # 'smart_playlist', etc.
    wizard_step: str = 'field'  # Current step: 'field', 'operator', 'value', 'conjunction', 'preview'
    wizard_data: dict[str, Any] = field(default_factory=dict)  # Wizard working data
    wizard_error: Optional[str] = None  # Error message for validation feedback
    wizard_selected: int = 0  # Selected option index (for arrow key navigation)
    wizard_options: list[str] = field(default_factory=list)  # Available options for current step

    # Track viewer state (for viewing and interacting with playlist tracks)
    track_viewer_visible: bool = False
    track_viewer_playlist_id: Optional[int] = None
    track_viewer_playlist_name: str = ""
    track_viewer_playlist_type: str = "manual"
    track_viewer_tracks: list[dict[str, Any]] = field(default_factory=list)
    track_viewer_selected: int = 0
    track_viewer_scroll: int = 0

    # Analytics viewer state (for viewing playlist analytics in full screen)
    analytics_viewer_visible: bool = False
    analytics_viewer_data: dict[str, Any] = field(default_factory=dict)  # Analytics data
    analytics_viewer_scroll: int = 0  # Scroll offset in lines
    analytics_viewer_total_lines: int = 0  # Total formatted lines (pre-calculated)

    # Metadata editor state (for editing track metadata interactively)
    editor_visible: bool = False
    editor_mode: str = 'main'  # 'main' | 'list_editor'
    editor_data: dict[str, Any] = field(default_factory=dict)  # All editor state in one dict
    editor_selected: int = 0  # Selected field/item index
    editor_scroll: int = 0  # Scroll offset
    editor_changes: dict[str, Any] = field(default_factory=dict)  # Pending changes

    # AI Review mode state (conversational tag review)
    review_mode: Optional[str] = None  # None, 'conversation', 'confirm'
    review_data: dict[str, Any] = field(default_factory=dict)  # Track, tags, conversation history

    # Library scan progress
    scan_progress: ScanProgress = field(default_factory=ScanProgress)

    # UI feedback (toast notifications)
    feedback_message: Optional[str] = None
    feedback_time: Optional[float] = None


def create_initial_state() -> UIState:
    """Create the initial UI state."""
    return UIState()


def update_track_info(state: UIState, track_data: dict[str, Any]) -> UIState:
    """Update track metadata and DB info."""
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
    """Add a line to command history and reset scroll to bottom."""
    new_history = state.history + [(text, color)]
    # Trim history if it exceeds max size
    if len(new_history) > MAX_COMMAND_HISTORY:
        new_history = new_history[-MAX_COMMAND_HISTORY:]
    # Reset scroll to bottom when new content added
    return replace(state, history=new_history, history_scroll=0)


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
    """Hide palette and reset selection."""
    return replace(state, palette_visible=False, palette_mode='command', palette_selected=0, palette_scroll=0, palette_query="")


def show_playlist_palette(state: UIState, items: list[tuple[str, str, str, str]]) -> UIState:
    """Show playlist palette with items."""
    return replace(state, palette_visible=True, palette_mode='playlist', palette_items=items, palette_selected=0, palette_scroll=0, palette_query="")


def update_palette_filter(state: UIState, query: str, items: list[tuple[str, str, str, str]]) -> UIState:
    """Update palette filter query and filtered items."""
    return replace(state, palette_query=query, palette_items=items, palette_selected=0, palette_scroll=0)


def move_palette_selection(state: UIState, delta: int, visible_items: int = 10) -> UIState:
    """
    Move palette selection up or down with scroll adjustment.

    Args:
        state: Current UI state
        delta: Direction and amount to move (-1 for up, 1 for down)
        visible_items: Number of items visible in viewport
    """
    if not state.palette_items:
        return state

    new_selected = (state.palette_selected + delta) % len(state.palette_items)

    # Adjust scroll to keep selection visible
    new_scroll = state.palette_scroll

    # Scroll down if selection goes below visible area
    if new_selected >= state.palette_scroll + visible_items:
        new_scroll = new_selected - visible_items + 1

    # Scroll up if selection goes above visible area
    elif new_selected < state.palette_scroll:
        new_scroll = new_selected

    return replace(state, palette_selected=new_selected, palette_scroll=new_scroll)


def show_confirmation(state: UIState, conf_type: str, data: dict[str, Any]) -> UIState:
    """Show confirmation dialog."""
    return replace(state, confirmation_active=True, confirmation_type=conf_type, confirmation_data=data)


def hide_confirmation(state: UIState) -> UIState:
    """Hide confirmation dialog."""
    return replace(state, confirmation_active=False, confirmation_type=None, confirmation_data=None)


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

    # Add command to history
    new_history = state.command_history + [command]

    # Enforce history size limit
    if len(new_history) > MAX_COMMAND_HISTORY:
        new_history = new_history[-MAX_COMMAND_HISTORY:]

    return replace(state, command_history=new_history, history_index=None, history_temp_input="")


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
        history_temp_input=new_temp_input
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
            history_index=new_index
        )
    else:
        # Reached newest command, restore saved input
        return replace(
            state,
            input_text=state.history_temp_input,
            cursor_pos=len(state.history_temp_input),
            history_index=None,
            history_temp_input=""
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


def start_wizard(state: UIState, wizard_type: str, initial_data: dict[str, Any]) -> UIState:
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
        wizard_step='field',
        wizard_data=initial_data,
        wizard_options=initial_options,
        wizard_selected=0,
        palette_visible=False,  # Hide palette when wizard starts
        input_text='',
        cursor_pos=0
    )


def update_wizard_step(state: UIState, step: str, options: list[str] | None = None) -> UIState:
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
        input_text='',
        cursor_pos=0,
        wizard_error=None,
        wizard_selected=0,
        wizard_options=options or []
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
        wizard_step='field',
        wizard_data={},
        wizard_error=None,
        wizard_selected=0,
        wizard_options=[],
        input_text='',
        cursor_pos=0
    )


def show_track_viewer(state: UIState, playlist_id: int, playlist_name: str, playlist_type: str, tracks: list[dict[str, Any]]) -> UIState:
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
        track_viewer_selected=0,
        track_viewer_scroll=0,
        palette_visible=False,  # Hide palette when viewer opens
        input_text='',
        cursor_pos=0
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
        track_viewer_playlist_name='',
        track_viewer_playlist_type='manual',
        track_viewer_tracks=[],
        track_viewer_selected=0,
        track_viewer_scroll=0
    )


def move_track_viewer_selection(state: UIState, delta: int, visible_items: int = 10) -> UIState:
    """
    Move track viewer selection up or down with scroll adjustment.

    Args:
        state: Current UI state
        delta: Direction and amount to move (-1 for up, 1 for down)
        visible_items: Number of items visible in viewport

    Returns:
        Updated state with new selection and scroll position
    """
    if not state.track_viewer_tracks:
        return state

    new_selected = (state.track_viewer_selected + delta) % len(state.track_viewer_tracks)

    # Adjust scroll to keep selection visible
    new_scroll = state.track_viewer_scroll

    # Scroll down if selection goes below visible area
    if new_selected >= state.track_viewer_scroll + visible_items:
        new_scroll = new_selected - visible_items + 1

    # Scroll up if selection goes above visible area
    elif new_selected < state.track_viewer_scroll:
        new_scroll = new_selected

    return replace(state, track_viewer_selected=new_selected, track_viewer_scroll=new_scroll)


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
    from music_minion.ui.blessed.components.analytics_viewer import format_analytics_lines

    try:
        term = Terminal()
        all_lines = format_analytics_lines(analytics_data, term)
        total_lines = len(all_lines)

        return replace(
            state,
            analytics_viewer_visible=True,
            analytics_viewer_data=analytics_data,
            analytics_viewer_scroll=0,
            analytics_viewer_total_lines=total_lines
        )
    except Exception as e:
        # On error, show error message in history instead of crashing UI
        error_msg = f"❌ Error formatting analytics: {e}"
        return add_history_line(state, error_msg, 'red')


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
        analytics_viewer_total_lines=0
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


def start_review_mode(state: UIState, track_data: dict[str, Any], tags_with_reasoning: dict[str, str]) -> UIState:
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
    conversation_lines.append(f"Track: {track_data.get('artist', 'Unknown')} - {track_data.get('title', 'Unknown')}")
    conversation_lines.append("")
    conversation_lines.append("Initial tags:")
    for tag, reasoning in tags_with_reasoning.items():
        conversation_lines.append(f"  • {tag}: \"{reasoning}\"")

    review_data = {
        'track': track_data,
        'initial_tags': tags_with_reasoning,
        'conversation_lines': conversation_lines
    }

    return replace(
        state,
        review_mode='conversation',
        review_data=review_data,
        input_text='',
        cursor_pos=0
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
    new_data = {**state.review_data, 'new_tags': new_tags}
    return replace(
        state,
        review_mode='confirm',
        review_data=new_data,
        input_text='',
        cursor_pos=0
    )


def exit_review_mode(state: UIState) -> UIState:
    """
    Exit review mode and reset state.

    Args:
        state: Current UI state

    Returns:
        Updated state with review mode exited
    """
    return replace(
        state,
        review_mode=None,
        review_data={},
        input_text='',
        cursor_pos=0
    )


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
        phase="scanning"
    )
    return replace(state, scan_progress=scan_progress)


def update_scan_progress(state: UIState, files_scanned: int, current_file: str, phase: str = "scanning") -> UIState:
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
        phase=phase
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
        editor_mode='main',
        editor_data=track_data,
        editor_selected=0,
        editor_scroll=0,
        editor_changes={},
        palette_visible=False,  # Hide palette when editor opens
        input_text='',
        cursor_pos=0
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
        editor_mode='main',
        editor_data={},
        editor_selected=0,
        editor_scroll=0,
        editor_changes={}
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


def set_editor_mode(state: UIState, mode: str, data: dict[str, Any] | None = None) -> UIState:
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
        return replace(state, editor_mode=mode, editor_data=new_data, editor_selected=0, editor_scroll=0)
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
    if change_type == 'basic':
        basic = new_changes.get('basic', {})
        new_changes['basic'] = {**basic, **change_data}
    else:
        # For list changes, append to list
        if change_type not in new_changes:
            new_changes[change_type] = []
        new_changes[change_type].append(change_data)

    return replace(state, editor_changes=new_changes)
