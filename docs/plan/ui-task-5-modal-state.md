# Task 5: Unified Modal State (Most Invasive)

## Goal
Consolidate 50+ modal fields into single `ModalState` structure.

## Files (15+ files affected)
- `src/music_minion/ui/blessed/state.py` (major changes)
- `src/music_minion/ui/blessed/app.py` (render dispatch)
- `src/music_minion/ui/blessed/events/keyboard.py` (mode detection)
- All files in `src/music_minion/ui/blessed/events/keys/`
- All files in `src/music_minion/ui/blessed/components/`

## Context
UIState currently has separate fields for each modal:
- `palette_visible`, `palette_selected`, `palette_scroll`, `palette_query`, `palette_items`, `palette_mode` (6 fields)
- `track_viewer_visible`, `track_viewer_playlist_id`, `track_viewer_tracks`, etc. (11 fields)
- Similar for: wizard, editor, analytics_viewer, rating_history, comparison_history, confirmation

Each `show_*()` function duplicates logic to close all other modals.

## Steps
1. Read `state.py` lines 96-279 to understand all modal fields
2. Design unified structure:
   ```python
   @dataclass
   class ModalState:
       modal_type: str = "none"  # 'palette', 'track_viewer', 'wizard', etc.
       selected: int = 0
       scroll: int = 0
       query: str = ""
       mode: str = "main"  # Sub-mode within modal
       data: dict = field(default_factory=dict)  # Modal-specific data
   ```
3. Replace individual fields in UIState:
   ```python
   # Before: 50+ fields
   # After:
   active_modal: ModalState = field(default_factory=ModalState)
   ```
4. Create unified show/hide:
   ```python
   def show_modal(state: UIState, modal_type: str, **data) -> UIState:
       return replace(state,
           active_modal=ModalState(modal_type=modal_type, data=data),
           input_text="", cursor_pos=0
       )

   def hide_modal(state: UIState) -> UIState:
       return replace(state, active_modal=ModalState())
   ```
5. Update `detect_mode()` in keyboard.py:
   ```python
   def detect_mode(state: UIState) -> str:
       if state.comparison.active:  # Comparison stays separate (special)
           return "comparison"
       return state.active_modal.modal_type or "normal"
   ```
6. Update all render functions to read from `state.active_modal`
7. Create render dispatcher:
   ```python
   MODAL_RENDERERS = {
       "palette": render_palette,
       "track_viewer": render_track_viewer,
       "wizard": render_smart_playlist_wizard,
       # ... etc
   }

   # In render loop:
   renderer = MODAL_RENDERERS.get(state.active_modal.modal_type)
   if renderer:
       renderer(term, state, layout)
   ```
8. Update all key handlers to use `state.active_modal` fields
9. Extensive testing of ALL 8 modal types

## Caution
This is the most invasive change. Do this AFTER tasks 1-4 are stable and committed. Consider doing in phases:
1. First add ModalState alongside existing fields
2. Migrate one modal at a time
3. Remove old fields after all modals migrated

## Success Criteria
- All 8 modals work correctly
- UIState has ~40 fewer fields
- Single `show_modal()`/`hide_modal()` mechanism
- Render dispatch uses dict instead of if/elif chain
