# Task 3: Generic List Viewer Component

## Goal
Extract shared rendering logic from rating_history and comparison_history (80% identical).

## Files
- New: `src/music_minion/ui/blessed/components/list_viewer.py`
- Modify: `src/music_minion/ui/blessed/components/rating_history.py`
- Modify: `src/music_minion/ui/blessed/components/comparison_history.py`
- Modify: `src/music_minion/ui/blessed/components/formatting.py`

## Context
Both history viewers are 210 lines each with identical structure:
- Header with title
- Separator line
- Empty state check
- List rendering loop with selection highlight
- Scroll indicator
- Footer with keybindings

The `_format_time_ago()` function is duplicated in both files (lines 174-210).

## Steps
1. Read both `rating_history.py` and `comparison_history.py` completely
2. Extract `_format_time_ago()` to `formatting.py`:
   ```python
   def format_time_ago(dt: datetime) -> str:
       """Format datetime as relative time string."""
       # ... existing implementation
   ```
3. Create `list_viewer.py`:
   ```python
   def render_list_viewer(
       term: Terminal,
       title: str,
       icon: str,
       items: list,
       selected: int,
       scroll: int,
       format_item: Callable[[Any, bool, Terminal], str],
       empty_message: str,
       footer_keys: str,
       y_start: int,
       height: int
   ) -> None:
       """Generic scrollable list viewer with selection."""
   ```
4. Refactor `rating_history.py`:
   ```python
   def render_rating_history_viewer(term, state, y, height):
       render_list_viewer(
           term, "Rating History", "📊",
           state.rating_history_ratings,
           state.rating_history_selected,
           state.rating_history_scroll,
           _format_rating_line,
           "No ratings yet",
           "[↑/↓] Navigate [Del/X] Remove [Esc] Close",
           y, height
       )
   ```
5. Same refactor for `comparison_history.py`
6. Delete duplicated code from both files
7. Test: `/rate history` and `/rate comparisons` display correctly

## Success Criteria
- Both viewers render identically to before
- `_format_time_ago` exists only in `formatting.py`
- ~170 lines of duplicate code removed
