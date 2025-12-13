# Metadata Editor Implementation Plan

## Overview
Create an interactive metadata editor command that allows editing all track metadata fields while music plays, with a nested viewer architecture for multi-value fields (ratings, notes, tags).

## Requirements Summary

### Editable Fields
- **Single-value fields**: title, artist, album, year, bpm, key, genre
- **Multi-value fields**: ratings, notes, tags

### User Experience
- Command: `metadata` - shows all metadata for current track
- Arrow key navigation through fields
- Enter to edit selected field
- Nested viewer for multi-value fields (ratings, notes, tags)
- Batch all changes and save when metadata viewer closes
- Async export to file metadata in background thread
- Success message in command history

### Nested Viewer Actions
- **Ratings**: View all historical ratings, edit type, delete specific rating, add new rating
- **Notes**: View all notes with timestamps, edit text, delete specific note, add new note
- **Tags**: View all tags with source/reasoning, add tag, remove tag

### Save Behavior
- Batch all database updates when metadata viewer closes
- Single transaction for all changes
- Trigger async `sync export` for the track
- Print success message to command history when export completes

## Components to Create/Modify

### 1. Database Layer (`src/music_minion/core/database.py`)
Add CRUD functions for metadata editing:

```python
def update_track_metadata(track_id: int, **fields) -> bool:
    """Update track metadata fields.

    Args:
        track_id: Track ID to update
        **fields: Field name/value pairs (title, artist, album, year, bpm, key_signature, genre)

    Returns:
        True if successful
    """
    # Build UPDATE query dynamically based on provided fields
    # Only update fields that are provided
    # Use COALESCE pattern for None values
    pass

def delete_rating(track_id: int, rating_timestamp: str) -> bool:
    """Delete specific rating by timestamp."""
    pass

def update_rating(track_id: int, old_timestamp: str, new_rating_type: str) -> bool:
    """Update rating type for a specific rating."""
    pass

def delete_note(track_id: int, note_timestamp: str) -> bool:
    """Delete specific note by timestamp."""
    pass

def update_note(track_id: int, old_timestamp: str, new_note_text: str) -> bool:
    """Update note text for a specific note."""
    pass

# Note: delete_tag already exists via remove_tag(track_id, tag_name)
```

### 2. UI State (`src/music_minion/ui/blessed/state.py`)

Add metadata viewer state to `UIState` dataclass:

```python
@dataclass
class UIState:
    # ... existing fields ...

    # Metadata viewer state
    metadata_viewer_visible: bool = False
    metadata_viewer_track_id: Optional[int] = None
    metadata_viewer_track_data: dict[str, Any] = field(default_factory=dict)
    metadata_viewer_selected: int = 0  # Selected field index in main viewer
    metadata_viewer_scroll: int = 0

    # Nested viewer state (for ratings, notes, tags)
    metadata_nested_active: bool = False
    metadata_nested_type: Optional[str] = None  # 'ratings' | 'notes' | 'tags'
    metadata_nested_items: list[dict[str, Any]] = field(default_factory=list)
    metadata_nested_selected: int = 0
    metadata_nested_scroll: int = 0

    # Pending changes (batch updates before save)
    metadata_pending_changes: dict[str, Any] = field(default_factory=dict)
    # Format: {
    #   'basic': {'title': 'New Title', 'artist': 'New Artist'},
    #   'ratings_to_delete': [timestamp1, timestamp2],
    #   'ratings_to_update': [(old_ts, new_type)],
    #   'ratings_to_add': [rating_type],
    #   'notes_to_delete': [timestamp],
    #   'notes_to_update': [(old_ts, new_text)],
    #   'notes_to_add': [note_text],
    #   'tags_to_delete': [tag_name],
    #   'tags_to_add': [tag_name],
    # }
```

State management functions:

```python
def show_metadata_viewer(state: UIState, track_id: int, track_data: dict) -> UIState:
    """Show metadata viewer with track data."""
    pass

def hide_metadata_viewer(state: UIState) -> UIState:
    """Hide metadata viewer and reset state."""
    pass

def move_metadata_selection(state: UIState, delta: int, visible_items: int = 10) -> UIState:
    """Move selection in main metadata viewer."""
    pass

def update_metadata_field(state: UIState, field: str, value: Any) -> UIState:
    """Update a metadata field in pending changes."""
    pass

def show_nested_viewer(state: UIState, nested_type: str, items: list) -> UIState:
    """Show nested viewer for multi-value fields."""
    pass

def hide_nested_viewer(state: UIState) -> UIState:
    """Hide nested viewer and return to main metadata viewer."""
    pass

def move_nested_selection(state: UIState, delta: int, visible_items: int = 10) -> UIState:
    """Move selection in nested viewer."""
    pass

def add_pending_change(state: UIState, change_type: str, data: Any) -> UIState:
    """Add a pending change to batch."""
    pass
```

### 3. Metadata Viewer Component (`src/music_minion/ui/blessed/components/metadata_viewer.py`)

Main rendering logic for the metadata viewer:

```python
"""Metadata viewer rendering for editing track metadata."""

from blessed import Terminal
from ..state import UIState

# Layout constants
METADATA_VIEWER_HEADER_LINES = 3  # Title + track info + separator
METADATA_VIEWER_FOOTER_LINES = 2  # Help text + blank

def render_metadata_viewer(term: Terminal, state: UIState, y: int, height: int) -> None:
    """
    Render metadata viewer with scrolling support.

    Shows all editable metadata fields:
    - Basic metadata: title, artist, album, year, bpm, key, genre
    - Multi-value: ratings (count), notes (count), tags (count)

    Args:
        term: blessed Terminal instance
        state: Current UI state
        y: Starting y position
        height: Available height for viewer
    """
    if not state.metadata_viewer_visible or height <= 0:
        return

    # Build field list from track data
    # Format: [(field_name, display_label, current_value, is_editable)]
    fields = build_metadata_fields(state.metadata_viewer_track_data)

    # Render header
    # Render scrollable field list with selection highlight
    # Render footer with keyboard shortcuts
    pass

def build_metadata_fields(track_data: dict) -> list[tuple[str, str, Any, bool]]:
    """Build list of metadata fields for display."""
    # Returns list of (field_name, display_label, value, is_editable)
    pass
```

### 4. Nested Viewers (`src/music_minion/ui/blessed/components/nested_viewers.py`)

Specialized rendering for multi-value fields:

```python
"""Nested viewers for multi-value metadata fields (ratings, notes, tags)."""

from blessed import Terminal
from ..state import UIState

def render_ratings_viewer(term: Terminal, state: UIState, y: int, height: int) -> None:
    """
    Render ratings nested viewer.

    Shows list of all ratings with:
    - Rating type (archive, like, love)
    - Timestamp
    - Context (if available)

    Actions: e: edit | d: delete | a: add | q: back
    """
    pass

def render_notes_viewer(term: Terminal, state: UIState, y: int, height: int) -> None:
    """
    Render notes nested viewer.

    Shows list of all notes with:
    - Note text (truncated if long)
    - Timestamp

    Actions: e: edit | d: delete | a: add | q: back
    """
    pass

def render_tags_viewer(term: Terminal, state: UIState, y: int, height: int) -> None:
    """
    Render tags nested viewer.

    Shows list of all tags with:
    - Tag name
    - Source (user/ai)
    - Reasoning (if available)

    Actions: d: delete | a: add | q: back
    """
    pass
```

### 5. Event Handlers (`src/music_minion/ui/blessed/events/commands/metadata_handlers.py`)

Keyboard event handling for metadata viewer:

```python
"""Metadata viewer event handlers."""

from music_minion.ui.blessed.state import UIState

def handle_metadata_viewer_key(state: UIState, event: dict) -> tuple[UIState | None, str | None]:
    """
    Handle keyboard events for metadata viewer.

    Main viewer:
    - Escape: Close viewer with save confirmation (if changes pending)
    - Arrow Up/Down or j/k: Navigate fields
    - Enter: Edit selected field (open nested viewer or edit in place)

    Nested viewer:
    - Escape or q: Back to main viewer
    - Arrow Up/Down or j/k: Navigate items
    - e: Edit selected item
    - d: Delete selected item
    - a: Add new item

    Returns:
        Tuple of (updated state or None, command to execute or None)
        Special commands: '__SAVE_METADATA__' triggers save and close
    """
    if state.metadata_nested_active:
        return handle_nested_viewer_key(state, event)
    else:
        return handle_main_viewer_key(state, event)

def handle_main_viewer_key(state: UIState, event: dict) -> tuple[UIState | None, str | None]:
    """Handle keyboard for main metadata viewer."""
    pass

def handle_nested_viewer_key(state: UIState, event: dict) -> tuple[UIState | None, str | None]:
    """Handle keyboard for nested viewer."""
    pass

def save_metadata_changes(state: UIState) -> bool:
    """
    Save all pending metadata changes to database.

    Process in order:
    1. Basic metadata updates
    2. Rating operations (delete, update, add)
    3. Note operations (delete, update, add)
    4. Tag operations (delete, add)

    Returns:
        True if successful
    """
    pass
```

### 6. Command Handler (`src/music_minion/commands/track.py`)

Add metadata command handler:

```python
def handle_metadata_command(ctx: AppContext, args: List[str]) -> Tuple[AppContext, bool]:
    """Handle metadata command - show metadata editor for current track.

    Args:
        ctx: Application context
        args: Command arguments (unused)

    Returns:
        (updated_context, should_continue)
    """
    if not ctx.player_state.current_track:
        print("No track is currently playing")
        return ctx, True

    # Get track from database
    db_track = database.get_track_by_path(ctx.player_state.current_track)
    if not db_track:
        print("❌ Could not find current track in database")
        return ctx, True

    track_id = db_track['id']

    # Load all metadata including ratings, notes, tags
    track_data = {
        'id': track_id,
        'file_path': db_track['file_path'],
        'title': db_track['title'],
        'artist': db_track['artist'],
        'album': db_track['album'],
        'year': db_track['year'],
        'bpm': db_track['bpm'],
        'key': db_track['key_signature'],
        'genre': db_track['genre'],
        'ratings': database.get_track_ratings(track_id),
        'notes': database.get_track_notes(track_id),
        'tags': database.get_track_tags(track_id, include_blacklisted=False),
    }

    # Show metadata viewer via internal command
    internal_cmd = InternalCommand(
        action='show_metadata_viewer',
        data={'track_id': track_id, 'track_data': track_data}
    )

    # Note: Actual UI state update happens in blessed event loop
    # This just signals the intent

    return ctx, True
```

### 7. Router Integration (`src/music_minion/router.py`)

Add routing for 'metadata' command:

```python
def handle_command(ctx: AppContext, command: str, args: List[str]) -> Tuple[AppContext, bool]:
    # ... existing commands ...

    elif command == 'metadata':
        return track.handle_metadata_command(ctx, args)

    # ... rest of commands ...
```

### 8. Command Palette (`src/music_minion/ui/blessed/styles/palette.py`)

Add to `COMMAND_DEFINITIONS`:

```python
COMMAND_DEFINITIONS: list[tuple[str, str, str, str]] = [
    # ... existing commands ...

    # Library
    ('🔍 Library', 'scan', '🔍', 'Scan library for new tracks'),
    ('🔍 Library', 'stats', '📊', 'Show library statistics'),
    ('🔍 Library', 'sync', '🔄', 'Sync metadata with files'),
    ('🔍 Library', 'metadata', '🔧', 'Edit track metadata'),  # NEW

    # ... rest of commands ...
]
```

### 9. Async Export Helper (`src/music_minion/helpers.py`)

Add async export function:

```python
import threading
from music_minion.domain.sync import engine as sync_engine

def async_export_single_track(track_id: int, ctx: AppContext) -> None:
    """
    Export single track metadata to file in background thread.

    Args:
        track_id: Track ID to export
        ctx: Application context
    """
    def _export():
        try:
            # Get track info
            with database.get_db_connection() as conn:
                cursor = conn.execute("SELECT file_path FROM tracks WHERE id = ?", (track_id,))
                row = cursor.fetchone()
                if not row:
                    return
                file_path = row['file_path']

            # Export tags to file metadata
            tags = [tag['tag_name'] for tag in database.get_track_tags(track_id)]
            success = sync_engine.write_tags_to_file(file_path, tags, ctx.config)

            if success:
                # Update file_mtime and last_synced_at
                new_mtime = sync_engine.get_file_mtime(file_path)
                with database.get_db_connection() as conn:
                    conn.execute(
                        "UPDATE tracks SET file_mtime = ?, last_synced_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (new_mtime, track_id)
                    )
                    conn.commit()

                print(f"✅ Metadata exported to file")
            else:
                print(f"⚠️ Metadata saved to database (file export disabled)")

        except Exception as e:
            print(f"❌ Error exporting metadata: {e}")

    # Run in background daemon thread
    export_thread = threading.Thread(
        target=_export,
        daemon=True,
        name="MetadataExportThread"
    )
    export_thread.start()
```

### 10. Keyboard Handler Integration (`src/music_minion/ui/blessed/events/keyboard.py`)

Add metadata viewer key handling to main `handle_key` function:

```python
def handle_key(state: UIState, key: Keystroke, term: Terminal) -> tuple[UIState, Optional[InternalCommand]]:
    """Main keyboard event dispatcher."""

    # ... existing handlers ...

    # Metadata viewer mode
    if state.metadata_viewer_visible:
        from .commands.metadata_handlers import handle_metadata_viewer_key
        new_state, command = handle_metadata_viewer_key(state, parse_key(key))
        if new_state:
            return new_state, InternalCommand(action=command) if command else None

    # ... rest of handlers ...
```

### 11. Dashboard Rendering Integration (`src/music_minion/ui/blessed/components/dashboard.py`)

Add metadata viewer rendering to dashboard:

```python
def render_full(term: Terminal, state: UIState) -> None:
    """Full dashboard render."""

    # ... existing rendering ...

    # Render metadata viewer if visible (takes priority over other overlays)
    if state.metadata_viewer_visible:
        from .metadata_viewer import render_metadata_viewer
        from .nested_viewers import render_ratings_viewer, render_notes_viewer, render_tags_viewer

        viewer_y = layout['command_palette_y']
        viewer_height = layout['command_palette_height']

        if state.metadata_nested_active:
            # Render nested viewer
            if state.metadata_nested_type == 'ratings':
                render_ratings_viewer(term, state, viewer_y, viewer_height)
            elif state.metadata_nested_type == 'notes':
                render_notes_viewer(term, state, viewer_y, viewer_height)
            elif state.metadata_nested_type == 'tags':
                render_tags_viewer(term, state, viewer_y, viewer_height)
        else:
            # Render main metadata viewer
            render_metadata_viewer(term, state, viewer_y, viewer_height)
```

## Implementation Flow

### User Experience Flow:
1. User plays a track
2. User types `metadata` command (or selects from command palette)
3. Full-screen metadata viewer opens (takes over command palette area)
4. Shows fields:
   ```
   📋 Metadata: Artist Name - Track Title

   Title:        Track Title
   Artist:       Artist Name
   Album:        Album Name
   Year:         2023
   BPM:          128
   Key:          Am
   Genre:        Electronic
   Ratings:      3 ratings ›
   Notes:        2 notes ›
   Tags:         5 tags ›

   [1/10] ↑↓ navigate  Enter edit  Esc close
   ```
5. User navigates with j/k or arrow keys (highlighted selection moves)
6. User presses Enter on "Ratings: 3 ratings ›"
7. Nested ratings viewer opens:
   ```
   📋 Ratings for Track Title

   ❤️  love         2025-01-15 14:32
   👍 like         2025-01-10 09:15
   👍 like         2025-01-05 18:45

   [1/3] ↑↓ navigate  e edit  d delete  a add  q back
   ```
8. User can: edit rating type, delete specific rating, add new rating
9. User presses 'q' to return to main metadata viewer
10. User edits other fields (title, artist, etc.) by pressing Enter and typing
11. User presses ESC to close metadata viewer
12. All changes are batched and saved to database in single transaction
13. Async export starts in background thread
14. Success message appears: "✅ Metadata saved and exported to file"

### Data Flow:
```
metadata command
    ↓
handle_metadata_command() - load track data
    ↓
show_metadata_viewer() - update UI state
    ↓
render_metadata_viewer() - display fields
    ↓
User navigates - move_metadata_selection()
    ↓
Enter on multi-value field → show_nested_viewer()
    ↓
render_nested_viewer() - show ratings/notes/tags
    ↓
User edits/deletes/adds → update pending_changes
    ↓
q to exit nested viewer → hide_nested_viewer()
    ↓
ESC to close main viewer → save_metadata_changes()
    ↓
Batch database updates (single transaction)
    ↓
async_export_single_track() in background thread
    ↓
Print success message to command history
```

## Architecture Patterns to Follow

### Immutable State
All state updates must use `dataclasses.replace()`:
```python
return replace(state, metadata_viewer_visible=True, metadata_viewer_track_id=track_id)
```

### Pure Rendering Functions
Signature: `(terminal, state, position) -> None`
- No side effects
- No database calls
- No state mutations
- Only read from state, write to terminal

### Functional Event Handlers
Signature: `(state, event) -> (new_state, command)`
- Return new state, never mutate
- Return command string for actions
- No direct database calls in handlers

### Explicit State Passing
Use `AppContext` for application-level state:
- Configuration
- Player state
- Music library
- Current track

Use `UIState` for UI-level state:
- Viewer visibility
- Selection indices
- Scroll positions
- Pending changes

### Single Responsibility
Each function should:
- Be ≤20 lines
- Have ≤3 nesting levels
- Do one thing well
- Have clear inputs/outputs

### Atomic Database Operations
When saving metadata:
```python
with get_db_connection() as conn:
    # 1. Update basic metadata
    conn.execute("UPDATE tracks SET ...")

    # 2. Delete ratings
    for ts in ratings_to_delete:
        conn.execute("DELETE FROM ratings WHERE ...")

    # 3. Update ratings
    for old_ts, new_type in ratings_to_update:
        conn.execute("UPDATE ratings SET ...")

    # 4. Add ratings
    for rating_type in ratings_to_add:
        conn.execute("INSERT INTO ratings ...")

    # ... same for notes and tags ...

    # Single commit at the end
    conn.commit()
```

### Error Handling
- Validate at entry points
- Fail fast for critical errors
- Graceful degradation for non-critical
- Always wrap background threads in try/except
- Include context in error messages

## Files Summary

### Files to Create (4 files):
1. `src/music_minion/ui/blessed/components/metadata_viewer.py` (~150 lines)
2. `src/music_minion/ui/blessed/components/nested_viewers.py` (~250 lines)
3. `src/music_minion/ui/blessed/events/commands/metadata_handlers.py` (~300 lines)
4. `docs/metadata-editor-plan.md` (this file)

### Files to Modify (7 files):
1. `src/music_minion/core/database.py` - Add 5 new functions (~100 lines)
2. `src/music_minion/ui/blessed/state.py` - Add state fields + 8 functions (~150 lines)
3. `src/music_minion/commands/track.py` - Add 1 function (~50 lines)
4. `src/music_minion/router.py` - Add 2 lines
5. `src/music_minion/ui/blessed/styles/palette.py` - Add 1 line
6. `src/music_minion/helpers.py` - Add 1 function (~50 lines)
7. `src/music_minion/ui/blessed/events/keyboard.py` - Add ~10 lines

### Total Estimated Lines of Code:
- New code: ~800 lines
- Modified code: ~215 lines
- **Total: ~1015 lines**

### Estimated Development Time:
- Database layer: 30 minutes
- UI state management: 45 minutes
- Metadata viewer component: 1 hour
- Nested viewers: 1.5 hours
- Event handlers: 1.5 hours
- Command integration: 30 minutes
- Testing & debugging: 1.5 hours
- **Total: 6-7 hours**

## Testing Checklist

- [ ] Can open metadata viewer while track is playing
- [ ] All fields display correctly with current values
- [ ] Navigation with arrow keys and j/k works
- [ ] Can edit single-value fields (title, artist, etc.)
- [ ] Can open nested viewer for ratings
- [ ] Can add/edit/delete individual ratings
- [ ] Can open nested viewer for notes
- [ ] Can add/edit/delete individual notes
- [ ] Can open nested viewer for tags
- [ ] Can add/delete individual tags
- [ ] Pending changes are tracked correctly
- [ ] ESC closes viewer with save confirmation
- [ ] All changes saved in single transaction
- [ ] Async export runs in background
- [ ] Success message appears after export
- [ ] Error handling works (no track playing, database errors, etc.)
- [ ] Works correctly with different track formats (MP3, M4A)
- [ ] UI doesn't flicker during navigation
- [ ] Scroll works correctly for long lists
- [ ] Can cancel changes by force-quitting viewer

## Future Enhancements

- [ ] Add undo/redo for metadata changes
- [ ] Add metadata history/audit log
- [ ] Support bulk editing multiple tracks
- [ ] Add metadata validation (e.g., year range, BPM range)
- [ ] Add autocomplete for genre, artist, album
- [ ] Add keyboard shortcuts for common actions (Ctrl+S to save)
- [ ] Add search/filter in nested viewers
- [ ] Support importing metadata from MusicBrainz/Discogs
- [ ] Add conflict detection if file was modified externally

---

**Last Updated**: 2025-10-05
**Status**: Planning phase
**Assigned to**: Claude Code
