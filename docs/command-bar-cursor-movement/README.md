# Command Bar Cursor Movement Implementation

## Overview

This implementation adds cursor movement within the command bar input text, allowing users to edit specific characters anywhere in the text instead of only appending/deleting at the end. This matches standard terminal/command-line behavior and significantly improves UX for command editing.

**Problem:** Currently, users must backspace entire words to fix typos because the cursor is always at the end of the input.

**Solution:** Enable left/right/home/end cursor navigation with visual feedback and horizontal scrolling for long inputs.

## Task Sequence

Execute tasks in numerical order:

1. [01-implement-state-cursor-functions.md](./01-implement-state-cursor-functions.md) - Core cursor movement and text editing state functions
2. [02-implement-keyboard-handlers.md](./02-implement-keyboard-handlers.md) - Arrow key routing and keyboard event handling
3. [03-implement-visual-cursor-rendering.md](./03-implement-visual-cursor-rendering.md) - Visual cursor display and horizontal scrolling
4. [04-handle-edge-cases-and-integration.md](./04-handle-edge-cases-and-integration.md) - Command history integration and boundary handling

## Success Criteria

### Functional Requirements

- ✅ Left/Right arrow keys move cursor within input text
- ✅ Home/End keys jump to start/end of input
- ✅ Text insertion works at any cursor position
- ✅ Backspace deletes character before cursor
- ✅ Delete key deletes character at cursor position
- ✅ Cursor visible at correct position in input area
- ✅ Horizontal scrolling for long inputs (> visible width)
- ✅ Command history navigation positions cursor at end of loaded command
- ✅ Cursor movement disabled in palette/filter modes (arrows navigate options)

### Technical Requirements

- ✅ All state functions are pure (return new UIState via `dataclasses.replace()`)
- ✅ Cursor position always within valid range `[0, len(input_text)]`
- ✅ Rendering uses Input tier (not Full tier) for performance
- ✅ Horizontal scrolling uses minimal scroll with 2-char margin
- ✅ No breaking changes to existing keyboard handling
- ✅ Edge cases handled: empty input, boundaries, palette modes

### Testing Requirements

- ✅ Unit tests for all cursor state functions
- ✅ Manual testing checklist completed for each task
- ✅ Edge case scenarios verified (boundaries, empty input, history)
- ✅ No crashes or out-of-bounds errors
- ✅ Smooth UX: cursor movements feel natural and responsive

## Execution Instructions

### Prerequisites

- Python environment set up with `uv`
- Music Minion CLI codebase accessible
- Familiarity with blessed terminal library

### Running Tests

```bash
# Run all tests
uv run pytest

# Run cursor-specific tests
uv run pytest tests/ui/blessed/test_state_cursor.py

# Run with coverage
uv run pytest --cov=src/music_minion/ui/blessed
```

### Manual Testing

After implementing all tasks, run the application and verify:

```bash
# Start the application
uv run music-minion

# Test cursor movement
1. Type "play foo bar"
2. Press left arrow 4 times (cursor at "foo|bar")
3. Type "baz" → should insert at cursor (becomes "play foobazbar")
4. Press backspace 3 times → deletes "baz"
5. Press Home → cursor jumps to start
6. Press End → cursor jumps to end
7. Press up arrow → loads previous command, cursor at end
8. Press "/" → opens palette, arrows navigate options (not cursor)
```

### Task Breakdown

Each task file contains:
- **Files to Modify/Create**: Exact file paths
- **Implementation Details**: Code snippets and logic explanations
- **Acceptance Criteria**: Checkboxes for completion verification
- **Dependencies**: Prerequisites from earlier tasks
- **Testing Strategy**: Unit tests and manual testing checklists

### Recommended Workflow

1. Read task file thoroughly
2. Implement code changes as specified
3. Run unit tests (if applicable)
4. Complete manual testing checklist
5. Verify acceptance criteria ✓
6. Move to next task

## Dependencies

### External Dependencies

- `blessed` - Python terminal library (already in project)
- `dataclasses` - Python standard library (for immutable state)

### Internal Dependencies

- **UIState dataclass** (`src/music_minion/ui/blessed/state.py`) - Must have `cursor_pos` field
- **Keyboard event handling** (`src/music_minion/ui/blessed/events/keys/normal.py`) - Event routing system
- **Input rendering** (`src/music_minion/ui/blessed/components/input.py`) - Visual display logic
- **write_at() helper** (`src/music_minion/ui/blessed/helpers/`) - Positioned terminal output

### Project Patterns

- **Immutable state**: All updates via `dataclasses.replace()`, never mutation
- **Pure functions**: `(UIState, ...) -> UIState` with no side effects
- **Functional over classes**: Prefer functions with explicit state passing
- **write_at() for rendering**: Always use positioned output to prevent overlap

## Architecture Notes

### State Management

- `cursor_pos` field tracks cursor position within `input_text`
- Invariant: `0 <= cursor_pos <= len(input_text)` (always enforced)
- Cursor at end: `cursor_pos == len(input_text)` (shows blank space cursor)

### Keyboard Event Routing

Arrow keys have conditional behavior:
- **Left/Right**: Cursor movement (when text exists, not in palette mode)
- **Up/Down**: History navigation (when text exists), seek controls (when empty)
- **Home/End**: Jump to start/end (when text exists, not in palette mode)

### Rendering Tiers

Music Minion uses three rendering tiers:
- **Full**: Complete screen redraw (track list, status, input)
- **Input**: Input area only (typing, cursor movement)
- **Partial**: Clock/progress only

Cursor movement triggers **Input tier** for performance.

### Horizontal Scrolling

Uses **minimal scroll with margin** strategy:
- Scroll only when cursor within 2 chars of edge or offscreen
- Keeps viewport stable (no jumping on every cursor move)
- Smooth scrolling experience for long inputs

## Benefits

- **Improved UX**: Edit anywhere in commands without retyping
- **Consistency**: Matches standard terminal behavior (readline, bash, zsh)
- **Efficiency**: Faster command correction (fix typo mid-word)
- **Accessibility**: More intuitive for users familiar with terminal editing
- **Polish**: Professional-grade command-line interface

## Implementation Decisions (from Plan Review)

These decisions were made during the plan review phase:

1. **Arrow key routing**: Left/right for cursor, up/down for history/seek (horizontal/vertical split)
2. **Palette mode behavior**: Cursor movement disabled (arrows navigate options only)
3. **Cursor position invariant**: Centralized `_clamp_cursor()` helper called by all state modifiers
4. **History navigation**: Always reset cursor to end (don't preserve per-entry)
5. **State function purity**: Explicit requirement to use `dataclasses.replace()`
6. **Rendering tier**: Input tier for cursor movement (not Full)
7. **Per-phase validation**: Unit tests after Phase 1, manual tests after each subsequent phase
8. **Function replacement**: Replace `append_input_char`/`delete_input_char` entirely (don't wrap)
9. **Horizontal scrolling**: Minimal scroll with 2-char margin
10. **Home/End keys**: Include in Phase 1 (not deferred)
11. **Call site audit**: Verified all 7 call sites safe for cursor-aware refactoring

## Notes

- Personal project: Breaking changes OK, no backwards compatibility required
- Codebase uses functional patterns: pure functions, immutable state, no classes
- Always use `uv run` for Python commands
- Logs: Use `logger.info()` for background, `log()` for user-facing
- Never use `print()` - breaks blessed UI
