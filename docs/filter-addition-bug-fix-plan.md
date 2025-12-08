# Playlist Builder Filter Addition Bug Fix - Implementation Plan

## Overview
Fix the bug where adding a new filter in playlist builder mode replaces the first filter instead of appending to the filters list with AND conjunction.

## Architecture Decisions

**Decision 1: Explicit Boolean Flag vs Sentinel Value**
- **Chosen**: Add dedicated `filter_editor_is_adding_new: bool` field to `PlaylistBuilderState`
- **Rationale**: The current approach uses `filter_editor_selected == -1` as a sentinel to indicate "adding new filter". However, `filter_editor_selected` serves dual purposes:
  1. During editing: Index into current step's options list (field/operator selection)
  2. During save: Flag to distinguish adding vs editing

  When advancing through the 3-step editing process (field → operator → value), `advance_filter_editor_step()` overwrites `filter_editor_selected` with option indices (lines 2227, 2243), destroying the original intent. An explicit boolean makes intent clear and survives step transitions.

**Decision 2: Dataclass Field Default**
- **Chosen**: Default `filter_editor_is_adding_new = False`
- **Rationale**: Most state resets should clear this flag. False is the safer default, requiring explicit True assignment only when initiating new filter addition.

## Root Cause Analysis

The bug occurs in this sequence:
1. `start_adding_filter()` (line 2193) sets `filter_editor_selected=-1` to indicate "adding new"
2. User advances through 3-step editing: field → operator → value
3. `advance_filter_editor_step()` overwrites the value:
   - Step 0→1 (line 2227): `filter_editor_selected=selected_op_idx`
   - Step 1→2 (line 2243): `filter_editor_selected=0`
4. `save_filter_editor_changes()` calls `_create_updated_filters()` (line 2291)
5. Since `filter_editor_selected == 0` (not `-1`), it replaces filter at index 0 instead of appending

## Implementation Tasks

### Phase 1: Add State Field
- [ ] Add `filter_editor_is_adding_new` boolean field to `PlaylistBuilderState`
  - Files: `src/music_minion/ui/blessed/state.py:140` (modify - add field to dataclass)
  - Location: In `PlaylistBuilderState` dataclass, after existing filter_editor fields
  - Code: `filter_editor_is_adding_new: bool = False`
  - Tests: None required (state definition)
  - Acceptance: Field exists with correct type and default value

### Phase 2: Set Flag on New Filter Addition
- [ ] Set `filter_editor_is_adding_new=True` in `start_adding_filter()`
  - Files: `src/music_minion/ui/blessed/state.py:2193` (modify - add field to replace() call)
  - Location: In the `replace()` call for `state.builder`
  - Code: Add line `filter_editor_is_adding_new=True,` after `filter_editor_editing=True,`
  - Tests: None required (will be verified in integration test)
  - Acceptance: Flag is set when adding new filter

### Phase 3: Clear Flag on Existing Filter Edit
- [ ] Set `filter_editor_is_adding_new=False` in `start_editing_filter()`
  - Files: `src/music_minion/ui/blessed/state.py:2150` (modify - add field to replace() call)
  - Location: In the `replace()` call for `builder`, around line 2165
  - Code: Add line `filter_editor_is_adding_new=False,` after `filter_editor_editing=True,`
  - Tests: None required (will be verified in integration test)
  - Acceptance: Flag is cleared when editing existing filter

### Phase 4: Update Filter Creation Logic
- [ ] Replace sentinel check with boolean flag in `_create_updated_filters()`
  - Files: `src/music_minion/ui/blessed/state.py:2291` (modify - change condition)
  - Location: First if condition in the function
  - Code: Change `if builder.filter_editor_selected == -1:` to `if builder.filter_editor_is_adding_new:`
  - Tests: None required (will be verified in integration test)
  - Acceptance: Logic uses new boolean flag instead of -1 sentinel

### Phase 5: Reset Flag on Exit
- [ ] Reset flag in `_exit_filter_editor_with_changes()`
  - Files: `src/music_minion/ui/blessed/state.py:2325` (modify - add field to replace() call)
  - Location: In the `replace()` call for `state.builder`
  - Code: Add line `filter_editor_is_adding_new=False,` after other filter_editor resets
  - Tests: None required (will be verified in integration test)
  - Acceptance: Flag is reset when exiting filter editor with changes

- [ ] Reset flag in `toggle_filter_editor_mode()` - exit path
  - Files: `src/music_minion/ui/blessed/state.py:2112` (modify - add field to replace() call)
  - Location: In the "Exit filter editor" branch, in `replace()` call for `state.builder`
  - Code: Add line `filter_editor_is_adding_new=False,` after other filter_editor resets
  - Tests: None required (will be verified in integration test)
  - Acceptance: Flag is reset when toggling filter editor off

- [ ] Reset flag in `toggle_filter_editor_mode()` - enter path
  - Files: `src/music_minion/ui/blessed/state.py:2127` (modify - add field to replace() call)
  - Location: In the "Enter filter editor" branch, in `replace()` call for `state.builder`
  - Code: Add line `filter_editor_is_adding_new=False,` after `filter_editor_mode=True,`
  - Tests: None required (will be verified in integration test)
  - Acceptance: Flag is initialized to False when entering filter editor mode

### Phase 6: Manual Integration Testing
- [ ] Test adding multiple filters in sequence
  - Verification Steps:
    1. Start music-minion in dev mode: `uv run music-minion --dev`
    2. Navigate to a manual playlist and press `b` to enter playlist builder
    3. Press `f` to open filter editor
    4. Press `a` to add new filter
    5. Select field (e.g., `genre`), operator (e.g., `equals`), value (e.g., `Dubstep`)
    6. Press Enter to save
    7. Press `a` again to add second filter
    8. Select field (e.g., `year`), operator (e.g., `<`), value (e.g., `2024`)
    9. Press Enter to save
  - Acceptance: Both filters appear in filter list (not replaced)

- [ ] Test filter AND logic application
  - Verification Steps:
    1. After adding filters from previous test
    2. Verify displayed tracks match BOTH conditions (genre=Dubstep AND year<2024)
  - Acceptance: Tracks are filtered with AND conjunction

- [ ] Test editing existing filter still works
  - Verification Steps:
    1. With filters from previous test visible
    2. Use j/k to select an existing filter
    3. Press Enter to edit it
    4. Change the value
    5. Press Enter to save
  - Acceptance: Selected filter is modified (not added as new), other filters unchanged

## Acceptance Criteria
- ✅ Adding a new filter appends to the filter list instead of replacing the first filter
- ✅ Multiple filters can be added in sequence
- ✅ Filters are applied with AND logic (all conditions must be true)
- ✅ Editing existing filters still works correctly
- ✅ Filter editor state is properly reset when exiting
- ✅ No Python type errors or runtime exceptions
- ✅ All existing functionality remains intact

## Files to Create/Modify

### Files to Modify
1. `src/music_minion/ui/blessed/state.py`
   - Line ~140: Add `filter_editor_is_adding_new` field to `PlaylistBuilderState`
   - Line 2112: Add flag reset in `toggle_filter_editor_mode()` exit path
   - Line 2127: Add flag reset in `toggle_filter_editor_mode()` enter path
   - Line 2165: Add `filter_editor_is_adding_new=False` in `start_editing_filter()`
   - Line 2193: Add `filter_editor_is_adding_new=True` in `start_adding_filter()`
   - Line 2291: Change condition from `== -1` to use boolean flag in `_create_updated_filters()`
   - Line 2325: Add flag reset in `_exit_filter_editor_with_changes()`

### Files to Create
None (bug fix only)

## Dependencies

### Internal Dependencies
- Must maintain backward compatibility with existing `PlaylistBuilderState` serialization (if any)
- No changes required to key handlers or render components
- No database schema changes required

### External Dependencies
None

## Implementation Notes

**Why not remove `filter_editor_selected`?**
- Still needed for tracking which option is selected during step editing (field/operator lists)
- Only the sentinel value check (-1) is problematic, not the field itself

**Migration concerns:**
- Adding a boolean field with default value is safe
- No existing code reads this field, so no compatibility issues
- If `PlaylistBuilderState` is persisted, old states will get `False` default automatically

**Edge cases handled:**
- Canceling filter edit (Escape key) - flag reset by `toggle_filter_editor_mode()`
- Toggling filter mode on/off - flag reset in both paths
- Invalid filter (missing field/operator) - validation prevents save, flag preserved
- Editing then canceling then adding new - flag correctly set on each operation

## Testing Strategy

Since this is a personal project with no automated test suite for UI interactions:
1. Manual testing workflow (detailed in Phase 6)
2. Verify no Python exceptions in logs
3. Test all filter operations: add, edit, delete, clear
4. Test mode transitions: enter/exit filter editor
5. Verify persistence across filter editor sessions

## Rollback Plan

If issues occur:
1. Revert all changes to `state.py`
2. Restore original `filter_editor_selected == -1` check in `_create_updated_filters()`
3. User can still use filters, just one at a time (current buggy behavior)
