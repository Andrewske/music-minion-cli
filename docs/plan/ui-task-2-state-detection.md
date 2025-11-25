# Task 2: Structured State Change Detection

## Goal
Replace magic tuple indices in `app.py` with proper dataclass comparison.

## Files
- `src/music_minion/ui/blessed/app.py`

## Context
Lines 704-726 initialize a 20-element tuple for tracking UI state changes. Lines 1041-1048 access elements by hardcoded index like `last_palette_state[7]` and `last_palette_state[19]`. This is fragile and bug-prone.

## Steps
1. Read lines 704-726 (tuple init) and 948-970 (tuple rebuild)
2. Read lines 1041-1048 to see magic index usage
3. Create frozen dataclass at top of file:
   ```python
   @dataclass(frozen=True)
   class RenderState:
       palette_visible: bool
       palette_selected: int
       wizard_active: bool
       wizard_selected: int
       track_viewer_visible: bool
       track_viewer_selected: int
       track_viewer_mode: str
       analytics_viewer_visible: bool
       analytics_viewer_scroll: int
       editor_visible: bool
       editor_selected: int
       editor_mode: str
       editor_input: str
       search_selected: int
       search_scroll: int
       search_mode: str
       search_detail_scroll: int
       search_detail_selection: int
       comparison_active: bool
       comparison_highlighted: str  # This was missing from tuple!
   ```
4. Add helper function:
   ```python
   def get_render_state(ui_state: UIState) -> RenderState:
       return RenderState(
           palette_visible=ui_state.palette_visible,
           # ... map all fields
       )
   ```
5. Replace tuple comparisons with `get_render_state(ui_state) != last_render_state`
6. Remove ALL magic index accesses
7. Test all modals open/close correctly

## Success Criteria
- No hardcoded tuple indices in codebase
- IDE catches field name typos
- `comparison_highlighted` now tracked (was missing)
