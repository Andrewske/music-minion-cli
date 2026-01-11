# Implement Visual Cursor Rendering with Horizontal Scrolling

## Files to Modify/Create
- `src/music_minion/ui/blessed/components/input.py` (modify)

## Implementation Details

### Update Cursor Rendering Logic

Replace the current rendering approach (always shows cursor at end) with cursor-position-aware rendering:

**Current approach:**
```python
prompt + input_text + cursor
```

**New approach:**
```python
before_cursor = input_text[:cursor_pos]
cursor_char = input_text[cursor_pos] if cursor_pos < len(input_text) else ' '
after_cursor = input_text[cursor_pos + 1:] if cursor_pos < len(input_text) else ''

rendered = prompt + before_cursor + cursor + after_cursor
```

### Implement Horizontal Scrolling

Use **minimal scroll with margin** strategy:
- Only scroll when cursor would be offscreen or within 2 chars of edge
- Scroll just enough to reveal cursor with 2-character margin
- Keeps viewport stable, prevents unnecessary jumping

```python
def _calculate_scroll_offset(
    cursor_pos: int,
    input_text: str,
    visible_width: int,
    current_offset: int = 0
) -> int:
    """Calculate horizontal scroll offset to keep cursor visible with margin."""
    MARGIN = 2

    # Cursor position relative to visible window
    cursor_in_window = cursor_pos - current_offset

    # Scroll right if cursor too far right (or past right edge)
    if cursor_in_window >= visible_width - MARGIN:
        # Shift offset right to reveal cursor with margin
        return cursor_pos - visible_width + MARGIN + 1

    # Scroll left if cursor too far left (or past left edge)
    if cursor_in_window < MARGIN:
        # Shift offset left to reveal cursor with margin
        return max(0, cursor_pos - MARGIN)

    # Cursor is comfortably visible, no scrolling needed
    return current_offset
```

### Update Input Component Rendering

Modify the input rendering function to:
1. Calculate scroll offset based on cursor position
2. Extract visible slice of input_text
3. Split visible text at cursor position
4. Render with cursor in correct position

```python
def render_input(
    term: Terminal,
    state: UIState,
    y_pos: int,
    max_width: int
) -> None:
    """Render input prompt and text with cursor at correct position."""
    prompt = "> "
    prompt_width = len(prompt)
    visible_width = max_width - prompt_width

    # Calculate scroll offset
    scroll_offset = _calculate_scroll_offset(
        cursor_pos=state.cursor_pos,
        input_text=state.input_text,
        visible_width=visible_width,
        current_offset=getattr(state, '_input_scroll_offset', 0)
    )

    # Extract visible portion of input
    visible_text = state.input_text[scroll_offset:scroll_offset + visible_width]

    # Cursor position within visible window
    cursor_pos_visible = state.cursor_pos - scroll_offset

    # Split text at cursor
    before_cursor = visible_text[:cursor_pos_visible]
    cursor_char = visible_text[cursor_pos_visible] if cursor_pos_visible < len(visible_text) else ' '
    after_cursor = visible_text[cursor_pos_visible + 1:] if cursor_pos_visible < len(visible_text) else ''

    # Render using write_at for positioned output
    write_at(term, y_pos, 0, prompt + before_cursor)
    write_at(term, y_pos, prompt_width + len(before_cursor), term.reverse(cursor_char))
    write_at(term, y_pos, prompt_width + len(before_cursor) + 1, after_cursor)

    # Store scroll offset in state for next frame (or track separately)
    # Note: May need to add _input_scroll_offset to UIState if not present
```

### Add Scroll Offset Tracking

If `UIState` doesn't have `_input_scroll_offset`, add it:

```python
# In state.py UIState dataclass
_input_scroll_offset: int = 0  # Horizontal scroll position for input text
```

Or track it locally in the input component if scroll state doesn't need to persist across renders.

### Handle Edge Cases

- **Empty input**: Render cursor as blank space at position 0
- **Cursor at end**: Render cursor as blank space after last character
- **Single character input**: before_cursor = "", cursor_char = char, after_cursor = ""
- **Very long input**: Only visible portion shown, scrolls smoothly as cursor moves

## Acceptance Criteria

- [ ] Cursor renders at correct position within input text
- [ ] Cursor visible when at start, middle, or end of input
- [ ] Horizontal scrolling activates for long inputs (> visible width)
- [ ] Scrolling uses minimal scroll with 2-char margin
- [ ] Viewport stable when cursor moves within comfortable zone
- [ ] Empty input shows cursor at position 0
- [ ] Cursor at end of input shows blank space cursor
- [ ] Input tier rendering triggered (not Full tier)
- [ ] Manual testing confirms smooth cursor movement and scrolling

## Dependencies

- Task 01: State cursor functions
- Task 02: Keyboard handlers

## Testing Strategy

Manual testing checklist:
1. Short input (< width): Type "hello" → move cursor → cursor visible at correct position
2. Long input (> width): Type 50-char string → move cursor to start → text scrolls to reveal start
3. Long input scrolling: Move cursor to end → text scrolls to reveal end
4. Margin behavior: Type long input → move cursor slowly → viewport scrolls at margins, not on every move
5. Empty input: Cursor visible at position 0 (blank space)
6. Character insertion: Insert 'x' mid-word → cursor moves right, character appears
7. Deletion: Delete mid-word → text collapses, cursor stays at position

## Technical Notes

- Use `write_at()` for all positioned output (clears line by default, prevents overlap)
- Ensure rendering triggers **Input tier** only, not Full tier (per Finding 6 in plan review)
- Scroll offset should persist during typing but reset when command is executed or cleared
