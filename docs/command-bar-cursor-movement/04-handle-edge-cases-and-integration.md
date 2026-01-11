# Handle Edge Cases and Command History Integration

## Files to Modify/Create
- `src/music_minion/ui/blessed/state.py` (modify)
- `src/music_minion/ui/blessed/events/keys/normal.py` (modify)

## Implementation Details

### Command History Navigation Integration

When loading commands from history (up/down arrows), cursor should jump to end of loaded command:

```python
def load_history_command(state: UIState, direction: str) -> UIState:
    """Load command from history and position cursor at end."""
    # ... existing history navigation logic ...

    # After loading new command into state.input_text
    state = replace(state, cursor_pos=len(state.input_text))

    return state
```

**Decision from plan review:** Always reset cursor to end when navigating history (Option 1 from Finding 4). Don't preserve cursor position per history entry.

### Cursor Position Invariant Enforcement

Add centralized cursor clamping to ensure `cursor_pos` stays within `[0, len(input_text)]`:

```python
def _clamp_cursor(state: UIState) -> UIState:
    """Ensure cursor_pos is within valid range [0, len(input_text)]."""
    clamped_pos = max(0, min(state.cursor_pos, len(state.input_text)))
    if clamped_pos != state.cursor_pos:
        return replace(state, cursor_pos=clamped_pos)
    return state
```

Call this helper:
- At the end of any function that modifies `input_text` (insertion, deletion, clear)
- After loading history commands
- When input is cleared (e.g., after command execution)

### Empty Input Handling

When input becomes empty, reset cursor to 0:

```python
def clear_input(state: UIState) -> UIState:
    """Clear input text and reset cursor."""
    return replace(state, input_text="", cursor_pos=0)
```

Ensure all places that clear input also reset cursor:
- After command execution
- When Escape key pressed
- When command palette closed without selection

### Palette/Filter Mode Cursor Behavior

From plan review (Finding 2, Option 1): **Disable cursor movement in palette/filter modes.**

Arrow keys should navigate options/filters only, not move cursor. This is already handled in Task 02 keyboard handlers (early return when `state.palette_visible`).

No additional changes needed, but verify:
- Cursor doesn't move when arrows pressed in palette mode
- Cursor position preserved when palette opened/closed
- Typing in filter mode still works (uses existing append logic)

### Bounds Checking Edge Cases

Test and verify these edge cases are handled correctly:

**Cursor at start:**
- Left arrow at position 0 → stays at 0
- Backspace at position 0 → no change
- Delete at position 0 → deletes first character, cursor stays at 0

**Cursor at end:**
- Right arrow at `len(input_text)` → stays at end
- Delete at `len(input_text)` → no change (nothing to delete)
- Typing at end → inserts and moves cursor right

**Empty input:**
- All cursor movements → cursor stays at 0
- Typing → inserts at 0, cursor moves to 1
- Backspace/delete → no change

**Cursor beyond bounds (should never happen, but defensive):**
- If `cursor_pos > len(input_text)` → clamped to `len(input_text)`
- If `cursor_pos < 0` → clamped to 0

### Input Text Modifications from Other Sources

Audit all places that modify `input_text` and ensure they handle cursor correctly:

**Places that set `input_text` directly:**
1. Command history navigation → cursor to end ✓
2. Command palette selection → cursor to end ✓
3. Wizard mode input → cursor to end ✓
4. Clear input → cursor to 0 ✓
5. Filter mode typing → cursor to end ✓

Add `_clamp_cursor()` call after any direct `input_text` modification.

## Acceptance Criteria

- [ ] Loading history commands positions cursor at end
- [ ] Cursor always within valid range `[0, len(input_text)]`
- [ ] Empty input handling: cursor at 0, movements do nothing
- [ ] Cursor at boundaries handled correctly (start/end)
- [ ] Palette/filter modes disable cursor movement (arrows navigate options)
- [ ] All input modifications clamp cursor to valid range
- [ ] Cursor reset to 0 when input cleared
- [ ] No crashes or out-of-bounds errors during edge case testing

## Dependencies

- Task 01: State cursor functions
- Task 02: Keyboard handlers
- Task 03: Visual rendering

## Testing Strategy

### Unit Tests

Add edge case tests to `tests/ui/blessed/test_state_cursor.py`:

```python
def test_cursor_clamped_when_text_deleted():
    # Cursor at position 5, delete all text
    state = UIState(input_text="hello", cursor_pos=5)
    state = replace(state, input_text="")
    state = _clamp_cursor(state)
    assert state.cursor_pos == 0

def test_delete_at_start():
    state = UIState(input_text="hello", cursor_pos=0)
    new_state = delete_char_before_cursor(state)
    assert new_state.input_text == "hello"  # No change
    assert new_state.cursor_pos == 0

def test_delete_key_at_end():
    state = UIState(input_text="hello", cursor_pos=5)
    new_state = delete_char_at_cursor(state)
    assert new_state.input_text == "hello"  # No change
    assert new_state.cursor_pos == 5
```

### Manual Testing Checklist

1. **History navigation:**
   - Type "play foo" → press up arrow → previous command loads, cursor at end
   - Press down arrow → returns to "play foo", cursor at end

2. **Empty input:**
   - Clear input → cursor at 0
   - Press left/right arrows → cursor stays at 0
   - Type 'x' → inserts at 0, cursor moves to 1

3. **Boundary testing:**
   - Cursor at start → press left → stays at 0
   - Cursor at start → press backspace → no change
   - Cursor at end → press right → stays at end
   - Cursor at end → press delete → no change

4. **Palette mode:**
   - Type "/" → palette opens
   - Press left/right arrows → navigate options, cursor doesn't move
   - Close palette → left/right arrows move cursor again

5. **Cursor clamping:**
   - Type "hello" (cursor at 5)
   - Select all text and delete → input empty, cursor at 0
   - No crashes or weird behavior

## Technical Notes

- All state modifications must use `dataclasses.replace()` (immutability)
- Call `_clamp_cursor()` after modifying `input_text` to maintain invariants
- History navigation uses existing functions, just ensure cursor reset added
- Palette mode cursor disabling already handled in Task 02 keyboard handlers
