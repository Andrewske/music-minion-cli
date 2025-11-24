# Split keyboard.py by Mode

## Problem

keyboard.py is 1,562 lines, making navigation difficult. File contains handlers for 10+ different modes (normal, wizard, palette, track_viewer, comparison, search, analytics, metadata_editor, rating_history). Each mode is 50-200 lines.

## Solution

Split into focused modules by mode. Keep all functions pure, maintain functional dispatch pattern. Only reorganize files, don't change architecture.

## Files to Create

- `src/music_minion/ui/blessed/events/keyboard_wizard.py`
- `src/music_minion/ui/blessed/events/keyboard_palette.py`
- `src/music_minion/ui/blessed/events/keyboard_track_viewer.py`
- `src/music_minion/ui/blessed/events/keyboard_comparison.py`
- `src/music_minion/ui/blessed/events/keyboard_rating_history.py`
- `src/music_minion/ui/blessed/events/keyboard_search.py`
- `src/music_minion/ui/blessed/events/keyboard_analytics.py`
- `src/music_minion/ui/blessed/events/keyboard_metadata_editor.py`
- `src/music_minion/ui/blessed/events/keyboard_normal.py`

## Files to Modify

- `src/music_minion/ui/blessed/events/keyboard.py` (becomes dispatcher only)

## Implementation Steps

1. **Extract mode handlers** to separate files:
   - Each file exports one main handler function
   - Copy helper functions used only by that mode
   - Keep shared utilities in keyboard.py or extract to keyboard_utils.py

2. **Main keyboard.py becomes clean dispatcher**:
   - Import all mode handlers
   - Keep `parse_key()` function
   - Keep `handle_key()` dispatcher
   - Remove mode-specific logic (now in separate files)

3. **Each mode file structure**:
   ```python
   # keyboard_wizard.py
   from music_minion.ui.blessed.state import UIState
   from music_minion.ui.blessed.events.commands.executor import InternalCommand

   def handle_wizard_key(state: UIState, event: dict) -> tuple[UIState, Optional[InternalCommand]]:
       # Pure function - mode-specific logic
   ```

4. **Maintain imports** - ensure all mode files can access:
   - State module
   - InternalCommand
   - Any shared utilities

5. **Update dispatcher** in keyboard.py:
   ```python
   from .keyboard_wizard import handle_wizard_key
   from .keyboard_palette import handle_palette_key
   # ... all mode imports

   def handle_key(state: UIState, key: Keystroke) -> tuple[UIState, Optional[InternalCommand]]:
       event = parse_key(key)

       if state.wizard_active:
           return handle_wizard_key(state, event)
       elif state.palette_visible:
           return handle_palette_key(state, event)
       # ... explicit dispatch
   ```

## Key Requirements

- **CRITICAL**: Maintain functional paradigm (no classes)
- Keep all functions pure
- No changes to function signatures
- All mode handlers return `tuple[UIState, Optional[InternalCommand]]`
- Maintain immutable state updates with `replace()`
- No behavioral changes

## Success Criteria

- keyboard.py reduced to ~150 lines (dispatcher only)
- Each mode file <200 lines
- All keyboard interactions work identically
- No test failures
- Easier to navigate and find mode-specific logic

## Testing

- Test all keyboard shortcuts in each mode
- Verify mode transitions work correctly
- Test edge cases (ESC, mode switching)
- Run full test suite
