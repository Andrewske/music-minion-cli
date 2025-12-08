# Filter Editor Bug Fixes and Improvements

**Created**: 2025-12-07
**Status**: Planning
**Priority**: Critical

## Overview

This document outlines fixes for critical bugs and improvements identified in commit 78dce252 (inline filter editor implementation). The current implementation has blocking bugs that prevent core functionality from working.

---

## Critical Bugs (MUST FIX)

### Bug 1: Broken Field Cycling Logic
**File**: `src/music_minion/ui/blessed/events/keys/playlist_builder.py:238-248`

**Issue**:
```python
if state.builder.filter_editor_field is None:
    fields = list(BUILDER_SORT_FIELDS)
    current_idx = 0
    if state.builder.filter_editor_field:  # ← ALWAYS False! Already checked None above
        try:
            current_idx = fields.index(state.builder.filter_editor_field)
        except ValueError:
            pass
    new_idx = (current_idx + 1) % len(fields)
```

**Impact**: Users stuck on first field only, cannot cycle through fields.

**Solution Options**:

**Option A - Initialize with first field**:
```python
# In start_editing_filter() and start_adding_filter()
filter_editor_field=BUILDER_SORT_FIELDS[0]  # Start with first field
```

**Option B - Use j/k for cycling** (RECOMMENDED):
- Remove "type any key to cycle" behavior
- Add explicit j/k navigation for field/operator selection
- Makes UX consistent with rest of app
- Add Enter to confirm and move to next step

**Recommendation**: Option B - aligns with app's navigation patterns and is more intuitive.

---

### Bug 2: Broken Operator Cycling Logic
**File**: `src/music_minion/ui/blessed/events/keys/playlist_builder.py:249-263`

**Issue**: Same pattern as Bug 1 - checks if operator is None, then immediately checks if it's truthy.

**Impact**: Users stuck on first operator only.

**Solution**: Same as Bug 1 - use Option B with j/k navigation.

---

### Bug 3: Dead State Fields
**File**: `src/music_minion/ui/blessed/state.py:142-150`

**Issue**: Old dropdown filter state still present:
```python
pending_filter_field: Optional[str] = None
pending_filter_operator: Optional[str] = None
filter_value_input: str = ""
```

**Impact**: Code clutter, confusion about which state is active.

**Solution**:
1. Remove these three fields from `PlaylistBuilderState`
2. Check for any remaining references in codebase
3. Remove related functions: `confirm_builder_filter`, `update_builder_filter_value`, `backspace_builder_filter_value`

**Search command**:
```bash
grep -r "pending_filter_field\|pending_filter_operator\|filter_value_input" src/
```

---

## Important Improvements

### Improvement 1: Redesign Filter Editing UX

**Current Flow** (broken):
1. Press 'e' on filter or 'a' to add
2. Type any printable character → cycles field
3. Type any printable character → cycles operator
4. Type characters → enters value
5. Enter to confirm

**Problems**:
- Confusing: typing has two meanings (cycle vs enter)
- No visual indication of current step
- Can't tell what key to press
- Inconsistent with sort dropdown (uses j/k)

**Proposed Flow** (clear, intuitive):

```
Step 1: Select Field
├─ Display: "Field: [title] ← Press j/k to select, Enter to confirm"
├─ j/k: cycle through BUILDER_SORT_FIELDS
└─ Enter: confirm field, move to step 2

Step 2: Select Operator
├─ Display: "Field: title | Operator: [contains] ← Press j/k to select, Enter to confirm"
├─ j/k: cycle through operators (text or numeric based on field)
└─ Enter: confirm operator, move to step 3

Step 3: Enter Value
├─ Display: "Field: title | Operator: contains | Value: [user_input_]"
├─ Type: regular text input
├─ Backspace: delete characters
└─ Enter: save filter, exit editing mode

At any step: Esc to cancel and return to filter list
```

**Implementation**:
- Add `filter_editor_step: int` field (0=select field, 1=select operator, 2=enter value)
- Separate key handlers for each step
- Clear visual indicators in render function

---

### Improvement 2: Break Down Large Function
**File**: `src/music_minion/ui/blessed/state.py:2321-2374`

**Issue**: `save_filter_editor_changes` is 53 lines (guideline: ≤20 lines)

**Solution**:
```python
def save_filter_editor_changes(state: UIState) -> UIState:
    """Save changes from filter editor and exit."""
    if not _validate_filter_edit(state.builder):
        return state

    new_filters = _create_updated_filters(state.builder)
    displayed = _rebuild_displayed_tracks(state.builder, new_filters)

    return _exit_filter_editor_with_changes(state, new_filters, displayed)


def _validate_filter_edit(builder: PlaylistBuilderState) -> bool:
    """Check if filter edit has required fields."""
    return bool(builder.filter_editor_field and builder.filter_editor_operator)


def _create_updated_filters(builder: PlaylistBuilderState) -> list[BuilderFilter]:
    """Create updated filter list with edited/new filter."""
    new_filter = BuilderFilter(
        field=builder.filter_editor_field,  # type: ignore
        operator=builder.filter_editor_operator,  # type: ignore
        value=builder.filter_editor_value,
    )

    if builder.filter_editor_selected == -1:
        return builder.filters + [new_filter]
    else:
        return (
            builder.filters[: builder.filter_editor_selected]
            + [new_filter]
            + builder.filters[builder.filter_editor_selected + 1 :]
        )


def _rebuild_displayed_tracks(
    builder: PlaylistBuilderState,
    new_filters: list[BuilderFilter]
) -> list[dict]:
    """Re-apply filters and sort to tracks."""
    displayed = _apply_builder_filters(builder.all_tracks, new_filters)
    return _apply_builder_sort(displayed, builder.sort_field, builder.sort_direction)


def _exit_filter_editor_with_changes(
    state: UIState,
    new_filters: list[BuilderFilter],
    displayed: list[dict]
) -> UIState:
    """Exit filter editor and apply changes."""
    return replace(
        state,
        builder=replace(
            state.builder,
            filters=new_filters,
            displayed_tracks=displayed,
            filter_editor_mode=False,
            filter_editor_selected=0,
            filter_editor_editing=False,
            filter_editor_field=None,
            filter_editor_operator=None,
            filter_editor_value="",
            selected_index=0,
            scroll_offset=0,
        ),
    )
```

---

### Improvement 3: Remove Dead Code
**File**: `src/music_minion/ui/blessed/components/playlist_builder.py:97-98`

**Issue**: Commented code left in place
```python
# Calculate visible range (for future use if needed)
# visible_end = min(scroll + height, len(tracks))
```

**Solution**: Delete lines 97-98 entirely.

---

### Improvement 4: Add Type Annotations
**File**: `src/music_minion/ui/blessed/components/playlist_builder.py`

**Missing annotations**:
- Line 54: `def _render_header(term: Terminal, builder, y: int) -> int:`
- Line 239: `def _render_filter_editor_header(term: Terminal, builder, y: int) -> int:`
- Line 250: `def _render_filter_list(term: Terminal, builder, y: int, height: int) -> int:`
- Line 300: `def _render_filter_editor_footer(term: Terminal, builder, y: int) -> int:`

**Solution**: Add `builder: PlaylistBuilderState` type annotation to all.

---

## Implementation Plan

### Phase 1: Critical Fixes (DO FIRST)
1. ✅ Create this planning document
2. Remove dead state fields from `PlaylistBuilderState`
   - Delete: `pending_filter_field`, `pending_filter_operator`, `filter_value_input`
   - Search and remove references
   - Remove unused functions: `confirm_builder_filter`, etc.
3. Add `filter_editor_step` field to state
4. Redesign filter editing key handler with stepped UX
   - Separate handlers for each step
   - j/k navigation for field/operator selection
   - Clear visual feedback
5. Update render function to show current step

### Phase 2: Code Quality (BEFORE MERGE)
6. Break down `save_filter_editor_changes` into helper functions
7. Remove commented dead code (line 97-98)
8. Add missing type annotations
9. Extract editing state formatter to helper function

### Phase 3: Testing (RECOMMENDED)
10. Manual testing of complete flow:
    - Add new filter (all field types)
    - Edit existing filter
    - Delete filter
    - Cancel at each step
    - Edge cases (empty filters list, etc.)
11. Consider unit tests for state transitions

---

## Testing Checklist

### Filter Addition
- [ ] Press 'a' enters add mode
- [ ] j/k cycles through fields correctly
- [ ] Enter confirms field, moves to operator step
- [ ] j/k cycles through correct operators (text vs numeric)
- [ ] Enter confirms operator, moves to value step
- [ ] Typing enters value normally
- [ ] Backspace deletes characters
- [ ] Enter saves filter and exits
- [ ] New filter appears in list
- [ ] Tracks are filtered correctly

### Filter Editing
- [ ] Press 'e' on existing filter loads its values
- [ ] Can change field
- [ ] Can change operator
- [ ] Can change value
- [ ] Changes are saved correctly
- [ ] Original filter is replaced, not duplicated

### Filter Deletion
- [ ] Press 'd' removes filter immediately
- [ ] Tracks update correctly
- [ ] Selection wraps appropriately

### Edge Cases
- [ ] Esc at each step cancels properly
- [ ] Empty filter list shows "[+] Add new filter"
- [ ] Pressing 'e' on "[+] Add" does nothing
- [ ] Numeric fields only show numeric operators
- [ ] Text fields only show text operators

---

## Files to Modify

1. `src/music_minion/ui/blessed/state.py`
   - Remove dead fields
   - Add `filter_editor_step` field
   - Refactor `save_filter_editor_changes`
   - Add step-based helper functions

2. `src/music_minion/ui/blessed/events/keys/playlist_builder.py`
   - Redesign `_handle_filter_editing_key`
   - Add step-based navigation logic
   - Remove broken cycling logic

3. `src/music_minion/ui/blessed/components/playlist_builder.py`
   - Update `_render_filter_list` to show step indicators
   - Add type annotations
   - Remove dead code
   - Extract formatting helpers

---

## Alternative Approaches Considered

### Alternative 1: Fix cycling logic as-is
**Approach**: Initialize fields on edit start, keep "type to cycle" UX
**Pros**: Minimal code changes
**Cons**: Still confusing UX, doesn't match app patterns
**Verdict**: ❌ Rejected - fixes bug but doesn't address UX issues

### Alternative 2: Dropdown with better architecture
**Approach**: Keep dropdown but fix threading issues
**Pros**: More familiar UI pattern
**Cons**: Already tried and failed (freezing issues)
**Verdict**: ❌ Rejected - original problem not solved

### Alternative 3: Stepped inline editor (SELECTED)
**Approach**: Clear step-by-step flow with consistent navigation
**Pros**:
- Intuitive, matches app patterns (j/k everywhere)
- Clear visual feedback at each step
- Resolves both bugs and UX issues
**Cons**: Requires more code changes
**Verdict**: ✅ **SELECTED** - Best long-term solution

---

## Success Criteria

- [ ] Users can successfully add filters with any field type
- [ ] Users can edit existing filters completely
- [ ] No dead/commented code remains
- [ ] All functions ≤20 lines (per guidelines)
- [ ] All parameters have type annotations
- [ ] Filter editing UX is intuitive and consistent with rest of app
- [ ] No console errors or exceptions during filter operations

---

## Notes

- Original commit attempted to fix freezing issues with dropdown
- Inline approach is sound, but implementation has critical bugs
- UX needs to be more deliberate and step-based
- This is personal project - can make breaking changes without migration path
