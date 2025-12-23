# Command Bar Cursor Movement Implementation Plan

## Problem Statement
The command bar currently only supports appending/deleting characters at the end of the input text. Users cannot move the cursor within the text to edit specific characters, requiring them to backspace entire words to fix typos.

## Root Cause Analysis
1. **State Tracking**: `cursor_pos` field exists but is always set to `len(input_text)`
2. **Input Functions**: All input operations (append/delete) work at string ends only
3. **Rendering**: Cursor always appears at end of text, ignoring `cursor_pos`
4. **Keyboard Handling**: Arrow keys only used for navigation/seek controls, not input editing

## Implementation Plan

### Phase 1: Core Cursor Movement Infrastructure

**1. Add cursor movement functions in `state.py`:**
- `move_cursor_left(state)` - Move cursor left by one character
- `move_cursor_right(state)` - Move cursor right by one character
- `move_cursor_home(state)` - Jump to start of input
- `move_cursor_end(state)` - Jump to end of input

**2. Add cursor-aware text editing functions:**
- `insert_char_at_cursor(state, char)` - Insert character at cursor position
- `delete_char_before_cursor(state)` - Backspace (delete before cursor)
- `delete_char_at_cursor(state)` - Delete key (delete at cursor)

**3. Update existing input functions to use cursor position:**
- Modify `append_input_char` to use `insert_char_at_cursor`
- Modify `delete_input_char` to use `delete_char_before_cursor`

### Phase 2: Keyboard Event Handling

**4. Add arrow key handlers in `normal.py`:**
- **Arrow Key Routing Rules:**
  - **Left/Right arrows**: Cursor movement within input text
  - **Up/Down arrows**: Command history navigation (takes priority over seek controls when input text exists)
  - **When input is empty**: Up/down arrows revert to seek controls (existing behavior)
- Handle `home` and `end` keys for line navigation (jump to start/end of input)
- **Palette/Filter Mode Exception**: Arrow keys navigate options/filters only, cursor movement disabled in these modes

**5. Update backspace/delete handling:**
- Use `delete_char_before_cursor` for backspace
- Use `delete_char_at_cursor` for delete key

### Phase 3: Visual Cursor Rendering

**6. Update input component (`input.py`):**
- Split `input_text` at `cursor_pos` for rendering
- Render as: `before_cursor + cursor_char + after_cursor`
- Implement horizontal scrolling that keeps cursor visible
- Update scrolling logic to prioritize cursor visibility over showing end of text

### Phase 4: Edge Cases & Polish

**7. Handle edge cases:**
- Cursor bounds checking (0 to `len(input_text)`)
- Empty input handling
- Command history navigation (cursor should go to end when loading history)
- Palette/filter interactions

**8. Update command history navigation:**
- When loading history with up/down arrows, position cursor at end of loaded command
- Preserve cursor position when navigating history temporarily

## Technical Details

### Files to Modify:
- `src/music_minion/ui/blessed/state.py` - Add cursor functions
- `src/music_minion/ui/blessed/events/keys/normal.py` - Add arrow key handling
- `src/music_minion/ui/blessed/components/input.py` - Update rendering logic

### Key Functions to Add:
```python
# In state.py
def move_cursor_left(state: UIState) -> UIState:
def move_cursor_right(state: UIState) -> UIState:
def insert_char_at_cursor(state: UIState, char: str) -> UIState:
def delete_char_before_cursor(state: UIState) -> UIState:
def delete_char_at_cursor(state: UIState) -> UIState:
```

### Rendering Logic Changes:
- Instead of: `prompt + input_text + cursor`
- New: `prompt + before_cursor + cursor + after_cursor`

### Keyboard Priority:
- Cursor movement only when `state.input_text` is not empty
- Seek controls remain active when input is empty (idle mode)

## Testing Considerations
- Basic cursor movement (left/right arrows)
- Text insertion at cursor position
- Backspace and delete at cursor
- Home/end key navigation
- Horizontal scrolling with cursor
- Command history integration
- Palette/filter mode compatibility

## Benefits
- **Improved UX**: Users can edit anywhere in commands without retyping
- **Consistency**: Matches standard terminal/command-line behavior
- **Efficiency**: Faster command correction and editing

## Implementation Status
- [ ] Phase 1: Core infrastructure
- [ ] Phase 2: Keyboard handling
- [ ] Phase 3: Visual rendering
- [ ] Phase 4: Edge cases & polish
- [ ] Testing & validation</content>
<parameter name="filePath">docs/command-bar-cursor-movement-plan.md