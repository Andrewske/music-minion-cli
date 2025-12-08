# Genre Selection Filter Implementation Plan

## Overview

Enhance the playlist builder filter editor to show a selectable list of genres when filtering by `genre` with the `equals` operator, instead of requiring manual text input. This improves UX by letting users pick from their library's actual genres.

## Architecture Decisions

- **Trigger condition**: Only show genre list for `genre` field + `equals` operator; other operators (contains, starts_with, etc.) keep text input for flexibility
- **Genre loading**: Query database for unique genres with counts, sorted by frequency descending
- **Display format**: Show genre name with count (e.g., "Electronic (145)") for context
- **State storage**: Reuse existing `filter_editor_options` for display strings, add new `filter_editor_genre_values` for raw values
- **Fallback**: If no genres exist in library, fall back to text input mode

## Implementation Tasks

### Phase 1: Database Layer

- [ ] Add `get_unique_genres()` function to database module
  - Files: `src/music_minion/core/database.py` (modify)
  - Tests: Manual verification via REPL
  - Acceptance: Returns list of `(genre, count)` tuples sorted by count descending, excludes NULL/empty genres

### Phase 2: State Layer

- [ ] Add `filter_editor_genre_values` field to `PlaylistBuilderState` dataclass
  - Files: `src/music_minion/ui/blessed/state.py` (modify, line ~166)
  - Tests: N/A (dataclass field)
  - Acceptance: New field with `list[str]` type and empty list default

- [ ] Modify `advance_filter_editor_step()` to load genres when transitioning to step 2
  - Files: `src/music_minion/ui/blessed/state.py` (modify)
  - Tests: Manual test in UI
  - Acceptance: When `field == "genre"` and `operator == "equals"`, populate `filter_editor_options` with formatted strings and `filter_editor_genre_values` with raw names

- [ ] Reset `filter_editor_genre_values` in cleanup functions
  - Files: `src/music_minion/ui/blessed/state.py` (modify)
  - Functions to update: `toggle_filter_editor_mode()`, `start_adding_filter()`, `start_editing_filter()`
  - Acceptance: Field resets to empty list when exiting or starting new filter edit

### Phase 3: Key Handler Layer

- [ ] Modify `_handle_filter_editing_key()` step 2 to support list navigation
  - Files: `src/music_minion/ui/blessed/events/keys/playlist_builder.py` (modify, line ~247)
  - Tests: Manual UI test
  - Acceptance:
    - When `filter_editor_options` is non-empty: j/k and arrow keys navigate list, Enter selects genre
    - When `filter_editor_options` is empty: existing text input behavior preserved

### Phase 4: Render Layer

- [ ] Modify `_render_filter_editing_steps()` step 2 to show list or text input
  - Files: `src/music_minion/ui/blessed/components/playlist_builder.py` (modify)
  - Tests: Manual UI test
  - Acceptance:
    - When `filter_editor_options` is non-empty: render selection list with genres
    - When empty: render text input field (existing behavior)

## Acceptance Criteria

- [ ] Adding filter with `genre` field + `equals` operator shows genre selection list
- [ ] Adding filter with `genre` field + `contains` operator shows text input (not list)
- [ ] Genre list displays counts (e.g., "Rock (42)")
- [ ] Navigation with j/k and arrow keys works in genre list
- [ ] Enter key selects genre and saves filter
- [ ] Filter correctly matches tracks after selection
- [ ] Empty library (no genres) gracefully falls back to text input
- [ ] Existing filters continue to work unchanged

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/music_minion/core/database.py` | Modify | Add `get_unique_genres()` function |
| `src/music_minion/ui/blessed/state.py` | Modify | Add field, modify step transition, update reset functions |
| `src/music_minion/ui/blessed/events/keys/playlist_builder.py` | Modify | Add list navigation for step 2 |
| `src/music_minion/ui/blessed/components/playlist_builder.py` | Modify | Conditional list vs text rendering |

## Dependencies

- Internal: `get_db_connection()` from database module
- Internal: `render_selection_list()` from `ui/blessed/helpers/selection.py` (existing, no changes needed)

## Code Snippets

### get_unique_genres() implementation

```python
def get_unique_genres() -> list[tuple[str, int]]:
    """Get all unique genres from tracks with counts.

    Returns:
        List of (genre, count) tuples, sorted by count descending.
        Excludes NULL/empty genres.
    """
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT genre, COUNT(*) as count
            FROM tracks
            WHERE genre IS NOT NULL AND genre != ''
            GROUP BY genre
            ORDER BY count DESC
        """)
        return [(row["genre"], row["count"]) for row in cursor.fetchall()]
```

### Step 2 key handling pattern

```python
elif step == 2:
    options = state.builder.filter_editor_options

    # Genre selection mode (list navigation)
    if options:
        if event_type == "key" and char in ("j", "k"):
            delta = 1 if char == "j" else -1
            new_idx = (state.builder.filter_editor_selected + delta) % len(options)
            return replace(state, builder=replace(state.builder, filter_editor_selected=new_idx)), None

        elif event_type in ("arrow_down", "arrow_up"):
            delta = 1 if event_type == "arrow_down" else -1
            new_idx = (state.builder.filter_editor_selected + delta) % len(options)
            return replace(state, builder=replace(state.builder, filter_editor_selected=new_idx)), None

        elif event_type == "enter":
            selected_genre = state.builder.filter_editor_genre_values[state.builder.filter_editor_selected]
            updated_state = replace(state, builder=replace(state.builder, filter_editor_value=selected_genre))
            return save_filter_editor_changes(updated_state), None

    # Text input mode (original behavior)
    else:
        # ... existing text input code unchanged ...
```

### Step transition genre loading

```python
# In advance_filter_editor_step(), elif step == 1 block:
genre_options: list[str] = []
genre_values: list[str] = []
if builder.filter_editor_field == "genre" and selected_operator_key == "equals":
    from music_minion.core.database import get_unique_genres
    genres = get_unique_genres()
    genre_options = [f"{genre} ({count})" for genre, count in genres]
    genre_values = [genre for genre, _ in genres]

return replace(
    state,
    builder=replace(
        builder,
        filter_editor_step=2,
        filter_editor_operator=selected_operator_key,
        filter_editor_options=genre_options,
        filter_editor_genre_values=genre_values,
        filter_editor_operator_keys=[],
        filter_editor_selected=0,
    ),
)
```
