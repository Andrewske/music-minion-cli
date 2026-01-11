# Implement State Cursor Movement Functions

## Files to Modify/Create
- `src/music_minion/ui/blessed/state.py` (modify)

## Implementation Details

### Add Cursor Movement Functions

Implement pure functions that return new `UIState` instances via `dataclasses.replace()`:

```python
def move_cursor_left(state: UIState) -> UIState:
    """Move cursor left by one character."""
    # Move cursor left, clamped to valid range
    new_pos = max(0, state.cursor_pos - 1)
    return replace(state, cursor_pos=new_pos)

def move_cursor_right(state: UIState) -> UIState:
    """Move cursor right by one character."""
    # Move cursor right, clamped to valid range
    new_pos = min(len(state.input_text), state.cursor_pos + 1)
    return replace(state, cursor_pos=new_pos)

def move_cursor_home(state: UIState) -> UIState:
    """Jump cursor to start of input."""
    return replace(state, cursor_pos=0)

def move_cursor_end(state: UIState) -> UIState:
    """Jump cursor to end of input."""
    return replace(state, cursor_pos=len(state.input_text))
```

### Add Cursor-Aware Text Editing Functions

```python
def insert_char_at_cursor(state: UIState, char: str) -> UIState:
    """Insert character at cursor position and move cursor right."""
    before = state.input_text[:state.cursor_pos]
    after = state.input_text[state.cursor_pos:]
    new_text = before + char + after
    new_pos = state.cursor_pos + 1
    return replace(state, input_text=new_text, cursor_pos=new_pos)

def delete_char_before_cursor(state: UIState) -> UIState:
    """Delete character before cursor (backspace)."""
    if state.cursor_pos == 0 or not state.input_text:
        return state
    before = state.input_text[:state.cursor_pos - 1]
    after = state.input_text[state.cursor_pos:]
    new_text = before + after
    new_pos = state.cursor_pos - 1
    return replace(state, input_text=new_text, cursor_pos=new_pos)

def delete_char_at_cursor(state: UIState) -> UIState:
    """Delete character at cursor position (delete key)."""
    if state.cursor_pos >= len(state.input_text) or not state.input_text:
        return state
    before = state.input_text[:state.cursor_pos]
    after = state.input_text[state.cursor_pos + 1:]
    new_text = before + after
    # Cursor position stays the same
    return replace(state, input_text=new_text)
```

### Replace Existing Functions

Replace `append_input_char` and `delete_input_char` entirely with cursor-aware implementations:

```python
def append_input_char(state: UIState, char: str) -> UIState:
    """Append character to input text at cursor position."""
    return insert_char_at_cursor(state, char)

def delete_input_char(state: UIState) -> UIState:
    """Delete character before cursor (backspace)."""
    return delete_char_before_cursor(state)
```

### Add Cursor Position Clamping Helper

Add a helper function to ensure cursor position stays within valid bounds:

```python
def _clamp_cursor(state: UIState) -> UIState:
    """Ensure cursor_pos is within valid range [0, len(input_text)]."""
    clamped_pos = max(0, min(state.cursor_pos, len(state.input_text)))
    if clamped_pos != state.cursor_pos:
        return replace(state, cursor_pos=clamped_pos)
    return state
```

Call this helper at the end of any function that modifies `input_text` to maintain invariants.

## Acceptance Criteria

- [ ] All cursor movement functions are pure (return new UIState via `dataclasses.replace()`)
- [ ] Cursor position is always clamped to valid range `[0, len(input_text)]`
- [ ] Text insertion works at any cursor position
- [ ] Backspace deletes character before cursor
- [ ] Delete key deletes character at cursor
- [ ] Edge cases handled: empty input, cursor at boundaries
- [ ] Unit tests pass for all new functions:
  - Cursor movement at boundaries (0, len(input_text))
  - Text insertion at start, middle, end
  - Deletion at start, middle, end
  - Empty input handling

## Dependencies

None - this is the foundation for all subsequent tasks.

## Testing Strategy

Write unit tests in a new test file `tests/ui/blessed/test_state_cursor.py`:

```python
def test_move_cursor_left():
    state = UIState(input_text="hello", cursor_pos=3)
    new_state = move_cursor_left(state)
    assert new_state.cursor_pos == 2

def test_move_cursor_left_at_start():
    state = UIState(input_text="hello", cursor_pos=0)
    new_state = move_cursor_left(state)
    assert new_state.cursor_pos == 0  # Stays at 0

def test_insert_char_at_cursor():
    state = UIState(input_text="helo", cursor_pos=3)
    new_state = insert_char_at_cursor(state, "l")
    assert new_state.input_text == "hello"
    assert new_state.cursor_pos == 4
```
