# Implement Keyboard Event Handlers for Cursor Movement

## Files to Modify/Create
- `src/music_minion/ui/blessed/events/keys/normal.py` (modify)

## Implementation Details

### Arrow Key Routing Rules

Implement conditional routing for arrow keys based on context:

**Left/Right Arrows:**
- Move cursor within input text when text exists
- Only active when `len(state.input_text) > 0`
- Disabled in palette/filter modes (arrows navigate options instead)

**Up/Down Arrows:**
- Command history navigation (takes priority when input text exists)
- Seek controls when input is empty (existing behavior)
- Disabled in palette/filter modes

### Add Left/Right Arrow Handlers

Add new handler functions in `normal.py`:

```python
def _handle_arrow_left(state: UIState, event: dict) -> tuple[UIState, None] | None:
    """Handle left arrow key for cursor movement."""
    if event["type"] != "arrow_left":
        return None

    # Disable cursor movement in palette/filter modes
    if state.palette_visible:
        return None

    # Only move cursor if there's input text
    if not state.input_text:
        return None

    state = move_cursor_left(state)
    return state, None


def _handle_arrow_right(state: UIState, event: dict) -> tuple[UIState, None] | None:
    """Handle right arrow key for cursor movement."""
    if event["type"] != "arrow_right":
        return None

    # Disable cursor movement in palette/filter modes
    if state.palette_visible:
        return None

    # Only move cursor if there's input text
    if not state.input_text:
        return None

    state = move_cursor_right(state)
    return state, None
```

### Add Home/End Key Handlers

```python
def _handle_home_key(state: UIState, event: dict) -> tuple[UIState, None] | None:
    """Handle Home key - jump to start of input."""
    if event["type"] != "home":
        return None

    # Disable in palette/filter modes
    if state.palette_visible:
        return None

    # Only active when there's input text
    if not state.input_text:
        return None

    state = move_cursor_home(state)
    return state, None


def _handle_end_key(state: UIState, event: dict) -> tuple[UIState, None] | None:
    """Handle End key - jump to end of input."""
    if event["type"] != "end":
        return None

    # Disable in palette/filter modes
    if state.palette_visible:
        return None

    # Only active when there's input text
    if not state.input_text:
        return None

    state = move_cursor_end(state)
    return state, None
```

### Update Backspace/Delete Handlers

Modify existing handlers to use cursor-aware functions:

```python
def _handle_backspace(state: UIState, event: dict) -> tuple[UIState, None] | None:
    """Handle backspace key (delete character before cursor)."""
    if event["type"] != "backspace":
        return None

    # Use cursor-aware delete function
    state = delete_char_before_cursor(state)
    state = reset_history_navigation(state)
    state = _update_palette_filter(state)
    return state, None


def _handle_delete_key(state: UIState, event: dict) -> tuple[UIState, None] | None:
    """Handle delete key (delete character at cursor or playlist)."""
    if event["type"] != "delete":
        return None

    # Delete playlist if in playlist palette mode
    if state.palette_visible and state.palette_mode == "playlist":
        if state.palette_items and state.palette_selected < len(state.palette_items):
            playlist_name = state.palette_items[state.palette_selected][1]
            state = show_confirmation(
                state, "delete_playlist", {"playlist_name": playlist_name}
            )
        return state, None
    else:
        # Use cursor-aware delete function (delete at cursor)
        state = delete_char_at_cursor(state)
        state = reset_history_navigation(state)
        state = _update_palette_filter(state)
        return state, None
```

### Register Handlers in Event Loop

Add new handlers to the handler chain in `handle_normal_key()`:

```python
def handle_normal_key(
    state: UIState, event: dict
) -> tuple[UIState, str | InternalCommand | None]:
    """Handle keyboard events for normal mode."""

    # ... existing handlers ...

    # Cursor movement handlers (add before existing handlers)
    result = _handle_arrow_left(state, event)
    if result is not None:
        return result

    result = _handle_arrow_right(state, event)
    if result is not None:
        return result

    result = _handle_home_key(state, event)
    if result is not None:
        return result

    result = _handle_end_key(state, event)
    if result is not None:
        return result

    # ... rest of handlers ...
```

## Acceptance Criteria

- [ ] Left/Right arrows move cursor when input text exists
- [ ] Left/Right arrows do nothing when input is empty
- [ ] Home/End keys jump to start/end of input
- [ ] Cursor movement disabled in palette/filter modes
- [ ] Backspace uses `delete_char_before_cursor()`
- [ ] Delete key uses `delete_char_at_cursor()` (when not deleting playlists)
- [ ] Up/Down arrows still navigate history when input exists
- [ ] Up/Down arrows revert to seek controls when input is empty
- [ ] Manual testing confirms expected behavior

## Dependencies

- Task 01: State cursor functions must be implemented first

## Testing Strategy

Manual testing checklist:
1. Type "play foo" → press left arrow 3 times → cursor at position 5
2. Press 'x' → inserts at cursor (becomes "play xfoo")
3. Press backspace → deletes 'x' (back to "play foo")
4. Press delete → deletes 'f' (becomes "play oo")
5. Press Home → cursor jumps to start
6. Press End → cursor jumps to end
7. Press up arrow → loads previous command, cursor at end
8. Press '/' to open palette → left/right arrows navigate options, not cursor
9. Close palette → left/right arrows move cursor again
