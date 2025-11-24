# Extract Common Scrolling Helpers

## Problem

Scrolling logic (selection movement, scroll offset calculation) is duplicated across palette, track_viewer, analytics_viewer, search mode, and rating history. Each implements similar math independently.

## Solution

Extract pure helper functions for common scrolling operations. Reuse across all list-based components while maintaining functional paradigm.

## Files to Create

- `src/music_minion/ui/blessed/helpers/scrolling.py` (NEW)

## Files to Modify

- `src/music_minion/ui/blessed/state.py` (update state updaters to use helpers)

## Implementation Steps

1. **Create helpers module** with pure functions:
   - `calculate_scroll_offset()` - Ensure selected item visible in viewport
   - `move_selection()` - Move selection with optional wrapping
   - `clamp_selection()` - Constrain selection to valid range

2. **Key helper signatures**:
   ```python
   def calculate_scroll_offset(
       selected: int,
       current_scroll: int,
       visible_items: int,
       total_items: int
   ) -> int:
       # Pure function - returns optimal scroll position

   def move_selection(
       current: int,
       delta: int,
       total_items: int,
       wrap: bool = True
   ) -> int:
       # Pure function - returns new selection index
   ```

3. **Update state.py functions** to use helpers:
   - `move_palette_selection()`
   - `move_track_viewer_selection()`
   - `move_search_selection()`
   - `move_analytics_viewer_selection()`
   - `move_rating_history_selection()`

4. **Import helpers** in state.py:
   ```python
   from music_minion.ui.blessed.helpers.scrolling import (
       calculate_scroll_offset,
       move_selection
   )
   ```

## Key Requirements

- All helpers must be pure functions (no state)
- Keep immutable pattern in state updaters
- Handle edge cases: empty lists, single item, wrap vs clamp
- Add comprehensive type hints
- Add docstrings with examples

## Success Criteria

- No duplication of scrolling logic
- All list views work identically
- Selection and scrolling behavior unchanged
- Code is more testable (isolated pure functions)

## Testing

- Unit test each helper function independently
- Test edge cases: 0 items, 1 item, exactly visible_items
- Verify all UI list views still work correctly
- Test wrapping vs clamping behavior
