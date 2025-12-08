# Filter Editor List Selection Implementation Guide

## Overview

Transform the playlist builder filter editor from a "cycle through with j/k" interface to a "select from list" interface by extracting and reusing the wizard's selection rendering code.

**Current State**: Inline cycling through options
```
1. genre ~ "dubstep" [1/3 Field: genre ← j/k to select, Enter to confirm]
```

**Target State**: Full list display with visual selection
```
Select field (j/k or ↑↓ arrows, Enter to confirm):
   ▶ title
     artist
     album
     genre  ← (current)
     year
     bpm
     key
```

## Implementation Steps

### Step 1: Extract Shared Selection Helper

**File**: `src/music_minion/ui/blessed/helpers/selection.py` (NEW)

Create a new helper module with the shared list rendering function:

```python
"""Shared selection list rendering helpers."""

from blessed import Terminal
from .terminal import write_at


def render_selection_list(
    term: Terminal,
    options: list[str],
    selected_idx: int,
    y: int,
    height: int,
    instruction: str = "",
) -> int:
    """
    Render a list of selectable options with highlighting.

    Used by both wizard and playlist builder for field/operator selection.

    Args:
        term: blessed Terminal instance
        options: List of option strings to display
        selected_idx: Index of currently selected option (0-based)
        y: Starting y position
        height: Available height
        instruction: Optional instruction text to show above options

    Returns:
        Number of lines rendered
    """
    if height <= 0:
        return 0

    line_num = 0

    # Show instruction if provided
    if instruction and line_num < height:
        write_at(term, 0, y + line_num, term.white(f"   {instruction}"))
        line_num += 1

    # Render options with highlighting
    for i, option in enumerate(options):
        if line_num >= height:
            break

        # Highlight selected option
        if i == selected_idx:
            prefix = "   ▶ "
            text = term.bold_green(option)
        else:
            prefix = "     "
            text = term.white(option)

        write_at(term, 0, y + line_num, prefix + text)
        line_num += 1

    return line_num
```

**Why**: This extracts the common pattern from wizard's `_render_field_step()` and `_render_operator_step()` into a single reusable function.

---

### Step 2: Refactor Wizard to Use Shared Helper

**File**: `src/music_minion/ui/blessed/components/wizard.py`

Add import at the top:
```python
from ..helpers.selection import render_selection_list
```

Replace `_render_field_step()` function (lines 116-149):
```python
def _render_field_step(term: Terminal, state: UIState, y: int, height: int) -> int:
    """Render field selection step with arrow key selection."""
    return render_selection_list(
        term,
        state.wizard_options,
        state.wizard_selected,
        y,
        height,
        instruction="Select field (↑↓ arrows, Enter to choose):",
    )
```

Replace `_render_operator_step()` function (lines 152-189):
```python
def _render_operator_step(term: Terminal, state: UIState, y: int, height: int) -> int:
    """Render operator selection step with arrow key selection."""
    wizard_data = state.wizard_data
    field = wizard_data.get('current_field', '')
    instruction = f"Select operator for '{field}' (↑↓ arrows, Enter to choose):"

    return render_selection_list(
        term,
        state.wizard_options,
        state.wizard_selected,
        y,
        height,
        instruction=instruction,
    )
```

Keep `_render_value_step()` unchanged (it handles text input, not list selection).

**Why**: Eliminates ~70 lines of duplicated code and ensures wizard continues to work identically.

---

### Step 3: Add State Field for Builder Options

**File**: `src/music_minion/ui/blessed/state.py`

In `PlaylistBuilderState` dataclass (around line 147), add:
```python
filter_editor_options: list[str] = field(default_factory=list)  # Available options for current step
```

**Why**: Stores the list of available options (fields or operators) for the current editing step, enabling list-based selection.

---

### Step 4: Update Builder State Functions

**File**: `src/music_minion/ui/blessed/state.py`

#### 4a. Update `start_editing_filter()` (around line 2147)

Replace the function to initialize options list:
```python
def start_editing_filter(state: UIState, filter_idx: int) -> UIState:
    """Start editing existing filter with list-based selection."""
    builder = state.builder
    if filter_idx >= len(builder.filters):
        return state

    selected_filter = builder.filters[filter_idx]
    field_options = sorted(list(BUILDER_SORT_FIELDS))

    # Find index of current field in options list
    selected_field_idx = 0
    if selected_filter.field in field_options:
        selected_field_idx = field_options.index(selected_filter.field)

    return replace(
        state,
        builder=replace(
            builder,
            filter_editor_editing=True,
            filter_editor_step=0,
            filter_editor_field=selected_filter.field,
            filter_editor_operator=selected_filter.operator,
            filter_editor_value=selected_filter.value,
            filter_editor_options=field_options,
            filter_editor_selected=selected_field_idx,  # Position at current field
        ),
    )
```

#### 4b. Update `start_adding_filter()` (around line 2164)

Replace to initialize options list:
```python
def start_adding_filter(state: UIState) -> UIState:
    """Start adding new filter with list-based selection."""
    field_options = sorted(list(BUILDER_SORT_FIELDS))

    return replace(
        state,
        builder=replace(
            state.builder,
            filter_editor_editing=True,
            filter_editor_step=0,
            filter_editor_field=None,
            filter_editor_operator=None,
            filter_editor_value="",
            filter_editor_options=field_options,
            filter_editor_selected=0,
        ),
    )
```

#### 4c. Add `advance_filter_editor_step()` (new function, add after `start_adding_filter()`)

```python
def advance_filter_editor_step(state: UIState) -> UIState:
    """Advance to next step and set appropriate options."""
    builder = state.builder
    step = builder.filter_editor_step

    if step == 0:
        # Moving from field to operator - set operator options based on field type
        selected_field = builder.filter_editor_options[builder.filter_editor_selected]

        if selected_field in BUILDER_NUMERIC_FIELDS:
            operator_options = [op[1] for op in BUILDER_NUMERIC_OPERATORS]
        else:
            operator_options = [op[1] for op in BUILDER_TEXT_OPERATORS]

        # Find current operator index (if editing existing filter)
        selected_op_idx = 0
        if builder.filter_editor_operator and builder.filter_editor_operator in operator_options:
            selected_op_idx = operator_options.index(builder.filter_editor_operator)

        return replace(
            state,
            builder=replace(
                builder,
                filter_editor_step=1,
                filter_editor_field=selected_field,
                filter_editor_options=operator_options,
                filter_editor_selected=selected_op_idx,
            ),
        )

    elif step == 1:
        # Moving from operator to value - clear options
        selected_operator = builder.filter_editor_options[builder.filter_editor_selected]
        return replace(
            state,
            builder=replace(
                builder,
                filter_editor_step=2,
                filter_editor_operator=selected_operator,
                filter_editor_options=[],
                filter_editor_selected=0,
            ),
        )

    return state
```

**Why**: These functions initialize the options list and handle advancing through steps while updating the selected field/operator based on user selection.

---

### Step 5: Update Builder Render Functions

**File**: `src/music_minion/ui/blessed/components/playlist_builder.py`

#### 5a. Add import at top:
```python
from ..helpers.selection import render_selection_list
```

#### 5b. Add `_render_filter_editing_steps()` (new function, add before `_render_filter_list()`)

```python
def _render_filter_editing_steps(
    term: Terminal, builder: PlaylistBuilderState, y: int, height: int
) -> int:
    """Render stepped editing interface with list selection."""
    step = builder.filter_editor_step

    if step == 0:
        # Show field selection list
        instruction = "Select field (j/k or ↑↓ arrows, Enter to confirm):"
        return render_selection_list(
            term,
            builder.filter_editor_options,
            builder.filter_editor_selected,
            y,
            height,
            instruction=instruction,
        )

    elif step == 1:
        # Show operator selection list
        field = builder.filter_editor_field
        instruction = f"Select operator for '{field}' (j/k or ↑↓ arrows, Enter to confirm):"
        return render_selection_list(
            term,
            builder.filter_editor_options,
            builder.filter_editor_selected,
            y,
            height,
            instruction=instruction,
        )

    elif step == 2:
        # Show value input (inline text entry, similar to wizard)
        line_num = 0

        if line_num < height:
            instruction = f"   Enter value for: {builder.filter_editor_field} {builder.filter_editor_operator}"
            write_at(term, 0, y + line_num, term.white(instruction))
            line_num += 1

        if line_num < height:
            value_line = f"   Value: {builder.filter_editor_value}_"
            write_at(term, 0, y + line_num, term.cyan(value_line))
            line_num += 1

        return line_num

    return 0
```

#### 5c. Modify `_render_filter_list()` (around line 246)

At the start of the function, add delegation to editing renderer:
```python
def _render_filter_list(
    term: Terminal, builder: PlaylistBuilderState, y: int, height: int
) -> int:
    """Render scrollable filter list or editing interface."""
    # If editing, show stepped selection UI instead of filter list
    if builder.filter_editor_editing:
        return _render_filter_editing_steps(term, builder, y, height)

    # Otherwise show normal filter list with filters + add option
    filters = builder.filters
    selected = builder.filter_editor_selected
    # ... (rest of existing logic)
```

**Why**: Separates the editing interface from the filter list view, using the shared selection helper for steps 0-1.

---

### Step 6: Update Builder Key Handler

**File**: `src/music_minion/ui/blessed/events/keys/playlist_builder.py`

Replace `_handle_filter_editing_key()` function (lines 208-301):

```python
def _handle_filter_editing_key(
    state: UIState,
    event: dict,
) -> tuple[Optional[UIState], Optional[Union[str, InternalCommand]]]:
    """Handle keys when editing a filter field/operator/value."""
    event_type = event.get("type")
    char = event.get("char", "")
    step = state.builder.filter_editor_step

    # Cancel editing
    if event_type == "escape":
        return replace(
            state,
            builder=replace(
                state.builder,
                filter_editor_editing=False,
                filter_editor_field=None,
                filter_editor_operator=None,
                filter_editor_value="",
                filter_editor_options=[],
                filter_editor_selected=0,
            ),
        ), None

    # Steps 0 & 1: List navigation with j/k or arrows
    if step in (0, 1):
        # j/k navigation
        if event_type == "key" and char in ("j", "k"):
            delta = 1 if char == "j" else -1
            options = state.builder.filter_editor_options
            if options:
                new_idx = (state.builder.filter_editor_selected + delta) % len(options)
                return replace(
                    state,
                    builder=replace(state.builder, filter_editor_selected=new_idx),
                ), None

        # Arrow key navigation
        elif event_type in ("arrow_down", "arrow_up"):
            delta = 1 if event_type == "arrow_down" else -1
            options = state.builder.filter_editor_options
            if options:
                new_idx = (state.builder.filter_editor_selected + delta) % len(options)
                return replace(
                    state,
                    builder=replace(state.builder, filter_editor_selected=new_idx),
                ), None

        # Enter: Advance to next step
        elif event_type == "enter":
            from ..state import advance_filter_editor_step
            return advance_filter_editor_step(state), None

    # Step 2: Value input
    elif step == 2:
        if event_type == "char" and char and char.isprintable():
            return replace(
                state,
                builder=replace(
                    state.builder,
                    filter_editor_value=state.builder.filter_editor_value + char,
                ),
            ), None

        elif event_type == "backspace" and state.builder.filter_editor_value:
            return replace(
                state,
                builder=replace(
                    state.builder,
                    filter_editor_value=state.builder.filter_editor_value[:-1],
                ),
            ), None

        elif event_type == "enter":
            # Save and exit editing
            from ..state import save_filter_editor_changes
            return save_filter_editor_changes(state), None

    return state, None
```

**Why**: Replaces field cycling logic with list navigation (j/k and arrows), using the options list stored in state.

---

## Testing Checklist

After implementation, test the following scenarios:

### Adding New Filter
- [ ] Press 'f' to enter filter editor
- [ ] Press 'a' to add new filter
- [ ] Verify full field list displays with all options visible
- [ ] Navigate with j → selection moves down, wraps at bottom
- [ ] Navigate with k → selection moves up, wraps at top
- [ ] Navigate with ↓ arrow → selection moves down
- [ ] Navigate with ↑ arrow → selection moves up
- [ ] Press Enter on field → advances to operator list
- [ ] Verify operator list shows correct operators for field type
  - Text field (title, artist, album, genre, key) → contains, equals, not_equals, starts_with, ends_with
  - Numeric field (year, bpm) → equals, not_equals, gt, lt, gte, lte
- [ ] Navigate operators with j/k or arrows
- [ ] Press Enter on operator → advances to value input
- [ ] Type value → characters appear
- [ ] Press Backspace → removes last character
- [ ] Press Enter → saves filter and returns to filter list
- [ ] Press Esc at any step → cancels and returns to filter list

### Editing Existing Filter
- [ ] Press 'f' to enter filter editor with existing filters
- [ ] Press 'e' on an existing filter
- [ ] Verify field list displays with current field highlighted
- [ ] Navigate to different field
- [ ] Press Enter → operator list updates based on new field type
- [ ] Verify current operator is highlighted if compatible
- [ ] Change operator
- [ ] Press Enter → value shows previous value
- [ ] Edit value
- [ ] Press Enter → filter updates with new values
- [ ] Verify filter list shows updated filter

### Visual Consistency
- [ ] Field list uses same style as wizard (▶ prefix, bold_green highlight)
- [ ] Operator list uses same style as wizard
- [ ] Value input shows cursor with underscore
- [ ] Instructions are clear and concise

### Edge Cases
- [ ] Empty value → pressing Enter should still save (or show error if invalid)
- [ ] Very long option names → don't break layout
- [ ] Switching from text to numeric field → operator list updates correctly
- [ ] Switching from numeric to text field → operator list updates correctly

---

## Files Modified Summary

| File | Type | Changes |
|------|------|---------|
| `helpers/selection.py` | NEW | Create shared selection list renderer (~50 lines) |
| `components/wizard.py` | REFACTOR | Replace `_render_field_step()` and `_render_operator_step()` (~70 lines → ~20 lines) |
| `state.py` | UPDATE | Add `filter_editor_options` field, update init functions, add `advance_filter_editor_step()` |
| `components/playlist_builder.py` | UPDATE | Add `_render_filter_editing_steps()`, modify `_render_filter_list()` |
| `events/keys/playlist_builder.py` | UPDATE | Replace `_handle_filter_editing_key()` with list navigation logic |

**Total Impact**:
- ~40 lines of duplicated code eliminated
- Guaranteed UX consistency between wizard and builder
- Single source of truth for selection rendering

---

## Constants Reference

From `state.py` (lines 1856-1875):

```python
BUILDER_SORT_FIELDS = ["title", "artist", "year", "album", "genre", "bpm", "key"]

BUILDER_NUMERIC_FIELDS = ["year", "bpm"]

BUILDER_TEXT_OPERATORS = [
    ("contains", "contains"),
    ("equals", "equals"),
    ("not_equals", "not_equals"),
    ("starts_with", "starts_with"),
    ("ends_with", "ends_with"),
]

BUILDER_NUMERIC_OPERATORS = [
    ("equals", "="),
    ("gt", ">"),
    ("lt", "<"),
    ("gte", ">="),
    ("lte", "<="),
    ("not_equals", "!="),
]
```

These constants define:
- Available fields for filtering
- Which fields are numeric (determines operator list)
- Available operators for text and numeric fields

---

## Implementation Notes

1. **Pure functions**: All render functions are pure (no side effects)
2. **Immutable updates**: All state changes use `dataclasses.replace()`
3. **Type safety**: All functions have type hints
4. **Consistent style**: Follow existing blessed UI patterns (write_at, terminal colors)
5. **Line limits**: Keep functions ≤20 lines where possible
6. **No global state**: Pass state explicitly

## Validation

After implementation:
1. Run the application with `uv run music-minion --dev`
2. Navigate to a manual playlist
3. Press 'b' to enter playlist builder
4. Press 'f' to enter filter editor
5. Test all scenarios from the checklist above
6. Verify no visual flicker or rendering issues
7. Verify filter logic still works correctly (tracks are filtered as expected)
