# Task 4: Unified Selection Movement

## Goal
Replace 15 similar selection movement functions with factory pattern.

## Files
- `src/music_minion/ui/blessed/state.py`

## Context
These functions all follow the same pattern:
- `move_palette_selection` (lines 505-526)
- `move_track_viewer_selection` (lines 888-917)
- `move_wizard_selection` (lines 778+)
- `move_editor_selection` (lines 1236+)
- `move_search_selection` (lines 1470-1497)
- `move_rating_history_selection` (lines 1601-1630)
- `move_comparison_history_selection` (lines 1722-1755)
- Plus scroll functions and action selection variants

Each does: `move_selection()` + `calculate_scroll_offset()` + `replace(state, field=value)`

## Steps
1. Search for all `def move_.*selection` in state.py
2. Create factory at top of file:
   ```python
   def create_selection_mover(
       selected_field: str,
       scroll_field: str,
       items_field: str
   ) -> Callable[[UIState, int, int], UIState]:
       """Factory for list selection movement functions."""
       def mover(state: UIState, delta: int, visible_items: int) -> UIState:
           items = getattr(state, items_field)
           if not items:
               return state
           current = getattr(state, selected_field)
           current_scroll = getattr(state, scroll_field)

           new_selected = move_selection(current, delta, len(items))
           new_scroll = calculate_scroll_offset(
               new_selected, current_scroll, visible_items, len(items)
           )

           return replace(state, **{
               selected_field: new_selected,
               scroll_field: new_scroll
           })
       return mover
   ```
3. Replace each function with factory call:
   ```python
   move_palette_selection = create_selection_mover(
       "palette_selected", "palette_scroll", "palette_items"
   )
   move_track_viewer_selection = create_selection_mover(
       "track_viewer_selected", "track_viewer_scroll", "track_viewer_filtered_tracks"
   )
   # ... etc
   ```
4. Verify all callers still work (they call the functions, signature unchanged)
5. Test arrow navigation in: palette, track viewer, wizard, editor, search, both history viewers

## Success Criteria
- All list navigation works identically
- ~150 lines of duplicate function bodies removed
- Single factory ensures consistent behavior
