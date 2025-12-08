# Genre Selection Filter with Shared Filter Editor

## Overview

1. Refactor filter editing to use shared components between Playlist Builder and Smart Playlist Wizard
2. Add genre selection list when filtering by `genre` + `equals` operator
3. Both systems benefit from the enhancement with no code duplication

## Current State

| System | Steps | Value Input | State Fields |
|--------|-------|-------------|--------------|
| Playlist Builder | 3 (field → op → value) | Text input | `filter_editor_*` in `PlaylistBuilderState` |
| Smart Playlist Wizard | 5 (field → op → value → conjunction → preview) | Text input | `wizard_*` fields in `UIState` |

Both use:
- Same field/operator definitions
- Same `render_selection_list()` helper
- Similar key handling patterns (j/k, arrows, Enter)

## Architecture Decision

**Create shared filter field/operator/value selector functions** that both systems call, rather than a new module. This keeps changes minimal while eliminating duplication.

Shared functions in `ui/blessed/helpers/filter_input.py`:
- `get_field_options()` → list of field names
- `get_operator_options(field)` → list of (key, display) tuples
- `get_value_options(field, operator)` → list of values for list selection, or empty for text input
- `render_filter_value_step()` → renders either list or text input
- `handle_filter_value_key()` → handles navigation/selection for value step

## Implementation Tasks

### Phase 1: Database Layer

- [x] Add `get_unique_genres()` function
  - Files: `src/music_minion/core/database.py` (modify)
  - Acceptance: Returns `list[tuple[str, int]]` sorted by count desc

### Phase 2: Shared Filter Input Helper

- [x] Create `src/music_minion/ui/blessed/helpers/filter_input.py`
  - Files: `src/music_minion/ui/blessed/helpers/filter_input.py` (new)
  - Functions:
    ```python
    def get_value_options(field: str, operator: str) -> tuple[list[str], list[str]]:
        """Returns (display_options, raw_values). Empty lists = text input mode."""
        if field == "genre" and operator == "equals":
            genres = get_unique_genres()
            return ([f"{g} ({c})" for g, c in genres], [g for g, _ in genres])
        return ([], [])

    def render_filter_value_input(
        term, field, operator, current_value, options, selected_idx, y, height
    ) -> int:
        """Render value step - list selection or text input."""

    def handle_filter_value_key(
        event, options, selected_idx, current_value
    ) -> tuple[int, str, bool]:
        """Handle key for value step. Returns (new_idx, new_value, should_save)."""
    ```
  - Acceptance: Reusable by both wizard and builder

### Phase 3: Playlist Builder Integration

- [x] Add `filter_editor_value_options` and `filter_editor_value_raw` fields to `PlaylistBuilderState`
  - Files: `src/music_minion/ui/blessed/state.py` (modify)

- [x] Modify `advance_filter_editor_step()` to call `get_value_options()`
  - Files: `src/music_minion/ui/blessed/state.py` (modify)
  - When transitioning to step 2, populate options if available

- [x] Update `_handle_filter_editing_key()` step 2 to use `handle_filter_value_key()`
  - Files: `src/music_minion/ui/blessed/events/keys/playlist_builder.py` (modify)

- [x] Update `_render_filter_editing_steps()` step 2 to use `render_filter_value_input()`
  - Files: `src/music_minion/ui/blessed/components/playlist_builder.py` (modify)

### Phase 4: Smart Playlist Wizard Integration

- [x] Update `handle_wizard_enter()` to call `get_value_options()` when entering value step
  - Files: `src/music_minion/ui/blessed/events/keys/wizard.py` (modify)
  - Store options in `wizard_options` when genre+equals

- [x] Update `handle_wizard_key()` value step handling
  - Files: `src/music_minion/ui/blessed/events/keys/wizard.py` (modify)
  - When `wizard_options` is set, use list navigation instead of text input

- [x] Update `_render_value_step()` to use `render_filter_value_input()`
  - Files: `src/music_minion/ui/blessed/components/wizard.py` (modify)

### Phase 5: Cleanup

- [x] Reset value options in cleanup functions for both systems
- [x] Update `__init__.py` to export new helper

## Files Summary

| File | Action | Description |
|------|--------|-------------|
| `src/music_minion/core/database.py` | Modify | Add `get_unique_genres()` |
| `src/music_minion/ui/blessed/helpers/filter_input.py` | **New** | Shared filter value selection logic |
| `src/music_minion/ui/blessed/helpers/__init__.py` | Modify | Export new module |
| `src/music_minion/ui/blessed/state.py` | Modify | Add value option fields to builder state |
| `src/music_minion/ui/blessed/events/keys/playlist_builder.py` | Modify | Use shared handler |
| `src/music_minion/ui/blessed/components/playlist_builder.py` | Modify | Use shared renderer |
| `src/music_minion/ui/blessed/events/keys/wizard.py` | Modify | Use shared handler, store options |
| `src/music_minion/ui/blessed/components/wizard.py` | Modify | Use shared renderer |

## Acceptance Criteria

- [x] Genre list appears for `genre` + `equals` in Playlist Builder
- [x] Genre list appears for `genre` + `equals` in Smart Playlist Wizard
- [x] Other operators still use text input
- [x] j/k and arrow navigation works in genre list
- [x] Enter selects genre and proceeds
- [x] No code duplication between systems

## Code Snippets

### get_unique_genres()

```python
def get_unique_genres() -> list[tuple[str, int]]:
    """Get all unique genres with counts, sorted by count desc."""
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

### Shared value options function

```python
def get_value_options(field: str, operator: str) -> tuple[list[str], list[str]]:
    """Get display options and raw values for filter value step.

    Returns:
        Tuple of (display_options, raw_values).
        Empty lists indicate text input mode.
    """
    if field == "genre" and operator == "equals":
        from music_minion.core.database import get_unique_genres
        genres = get_unique_genres()
        if genres:
            return (
                [f"{genre} ({count})" for genre, count in genres],
                [genre for genre, _ in genres]
            )
    return ([], [])
```

### Shared key handler

```python
def handle_filter_value_key(
    event: dict,
    options: list[str],
    selected_idx: int,
    current_value: str
) -> tuple[int, str, bool]:
    """Handle keyboard input for filter value step.

    Returns:
        Tuple of (new_selected_idx, new_value, should_save).
    """
    event_type = event.get("type")
    char = event.get("char", "")

    # List selection mode
    if options:
        if event_type == "key" and char in ("j", "k"):
            delta = 1 if char == "j" else -1
            return ((selected_idx + delta) % len(options), current_value, False)
        if event_type in ("arrow_down", "arrow_up"):
            delta = 1 if event_type == "arrow_down" else -1
            return ((selected_idx + delta) % len(options), current_value, False)
        if event_type == "enter":
            return (selected_idx, current_value, True)  # Caller extracts raw value

    # Text input mode
    else:
        if event_type == "char" and char and char.isprintable():
            return (selected_idx, current_value + char, False)
        if event_type == "backspace":
            return (selected_idx, current_value[:-1], False)
        if event_type == "enter":
            return (selected_idx, current_value, True)

    return (selected_idx, current_value, False)
```
