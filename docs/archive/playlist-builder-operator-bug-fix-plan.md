# Playlist Builder Filter Operator Bug Fix - Implementation Plan

## Overview
Fix critical bug where playlist builder filters show 0 results due to operator key/display value mismatch. The filter editor stores operator display values (like `"<"`, `">"`) instead of operator keys (like `"lt"`, `"gt"`), causing filter matching to fail for numeric operators.

## Root Cause Analysis

**Current Broken Flow:**
1. `advance_filter_editor_step()` extracts display values from operator tuples (`op[1]`)
   - Numeric: `["=", ">", "<", ">=", "<=", "!="]`
   - Text: `["contains", "equals", "not equals", "starts with", "ends with"]`
2. Stores display value directly as the operator (e.g., `"<"` instead of `"lt"`)
3. `_matches_builder_filter()` expects operator keys in its lookup dict
   - Has keys: `"equals"`, `"gt"`, `"lt"`, `"gte"`, `"lte"`, `"not_equals"`
   - Lookup fails: `ops.get("<", False)` returns `False` (should use `"lt"`)
4. Zero tracks match, breaking AND filter logic

**User Impact:** Filters like `year < 2024 AND genre contains dubstep` return 0 results instead of hundreds of tracks.

## Architecture Decisions

**Decision 1: Parallel Key List vs Reverse Lookup**
- **Chosen:** Maintain parallel list of operator keys alongside display values
- **Rationale:**
  - Cleaner separation: Display values for UI, keys for storage
  - No lookup overhead during save
  - Explicit intent - easier to understand and maintain
- **Alternative:** Reverse lookup from display to key (rejected: adds complexity)

**Decision 2: Field Location**
- **Chosen:** Add `filter_editor_operator_keys` to `PlaylistBuilderState` after `filter_editor_options`
- **Rationale:** Groups related editor state fields together

**Decision 3: Migration Strategy**
- **Chosen:** No automatic migration - users re-create broken filters
- **Rationale:** Personal project, no compatibility requirements, simple fix

## Implementation Tasks

### Phase 1: State Structure Update
- [ ] Add operator keys field to PlaylistBuilderState
  - Files: `src/music_minion/ui/blessed/state.py:158` (modify - add field)
  - Location: In `PlaylistBuilderState` dataclass, after `filter_editor_options` field
  - Code: `filter_editor_operator_keys: list[str] = field(default_factory=list)`
  - Tests: None required (state definition)
  - Acceptance: Field exists with correct type and default value

### Phase 2: Operator Key Extraction and Storage
- [ ] Extract operator keys alongside display values in step 0→1 transition
  - Files: `src/music_minion/ui/blessed/state.py:2217-2220` (modify - add key extraction)
  - Current Code:
    ```python
    if selected_field in BUILDER_NUMERIC_FIELDS:
        operator_options = [op[1] for op in BUILDER_NUMERIC_OPERATORS]
    else:
        operator_options = [op[1] for op in BUILDER_TEXT_OPERATORS]
    ```
  - New Code:
    ```python
    if selected_field in BUILDER_NUMERIC_FIELDS:
        operator_options = [op[1] for op in BUILDER_NUMERIC_OPERATORS]
        operator_keys = [op[0] for op in BUILDER_NUMERIC_OPERATORS]
    else:
        operator_options = [op[1] for op in BUILDER_TEXT_OPERATORS]
        operator_keys = [op[0] for op in BUILDER_TEXT_OPERATORS]
    ```
  - Tests: Manual testing (Phase 6)
  - Acceptance: Both display values and keys extracted correctly

- [ ] Store operator keys in state during step 0→1 transition
  - Files: `src/music_minion/ui/blessed/state.py:2230-2239` (modify - add field to replace())
  - Location: In `advance_filter_editor_step()`, step 0 branch return statement
  - Add to replace() call: `filter_editor_operator_keys=operator_keys,`
  - Tests: Manual testing (Phase 6)
  - Acceptance: Operator keys stored in state alongside display values

### Phase 3: Save Operator Key Instead of Display Value
- [ ] Update step 1→2 transition to save operator key
  - Files: `src/music_minion/ui/blessed/state.py:2241-2255` (modify - change selected value)
  - Current Code:
    ```python
    selected_operator = builder.filter_editor_options[builder.filter_editor_selected]
    return replace(
        state,
        builder=replace(
            builder,
            filter_editor_step=2,
            filter_editor_operator=selected_operator,  # Stores display!
            filter_editor_options=[],
            filter_editor_selected=0,
        ),
    )
    ```
  - New Code:
    ```python
    selected_operator_key = builder.filter_editor_operator_keys[builder.filter_editor_selected]
    return replace(
        state,
        builder=replace(
            builder,
            filter_editor_step=2,
            filter_editor_operator=selected_operator_key,  # Store key!
            filter_editor_options=[],
            filter_editor_operator_keys=[],  # Clear keys
            filter_editor_selected=0,
        ),
    )
    ```
  - Tests: Manual testing (Phase 6)
  - Acceptance: Operator key stored instead of display value

### Phase 4: Fix Operator Index Lookup for Editing
- [ ] Update operator index lookup to use keys instead of display values
  - Files: `src/music_minion/ui/blessed/state.py:2222-2228` (modify - change lookup logic)
  - Current Code:
    ```python
    selected_op_idx = 0
    if (
        builder.filter_editor_operator
        and builder.filter_editor_operator in operator_options
    ):
        selected_op_idx = operator_options.index(builder.filter_editor_operator)
    ```
  - New Code:
    ```python
    selected_op_idx = 0
    if builder.filter_editor_operator:
        try:
            selected_op_idx = operator_keys.index(builder.filter_editor_operator)
        except ValueError:
            selected_op_idx = 0  # Key not found, default to first
    ```
  - Tests: Manual testing (Phase 6)
  - Acceptance: Editing existing filter shows correct operator selected

### Phase 5: Reset Operator Keys on State Transitions
- [ ] Reset operator keys when exiting filter editor (toggle off)
  - Files: `src/music_minion/ui/blessed/state.py:2112-2124` (modify - add field reset)
  - Location: In `toggle_filter_editor_mode()`, exit branch
  - Add to replace() call: `filter_editor_operator_keys=[],`
  - Tests: Manual testing (Phase 6)
  - Acceptance: Operator keys cleared when toggling off

- [ ] Reset operator keys when entering filter editor (toggle on)
  - Files: `src/music_minion/ui/blessed/state.py:2127-2139` (modify - add field reset)
  - Location: In `toggle_filter_editor_mode()`, enter branch
  - Add to replace() call: `filter_editor_operator_keys=[],`
  - Tests: Manual testing (Phase 6)
  - Acceptance: Operator keys initialized empty when toggling on

- [ ] Reset operator keys when saving filter changes
  - Files: `src/music_minion/ui/blessed/state.py:2325-2346` (modify - add field reset)
  - Location: In `_exit_filter_editor_with_changes()`, replace() call
  - Add to replace() call: `filter_editor_operator_keys=[],`
  - Tests: Manual testing (Phase 6)
  - Acceptance: Operator keys cleared after saving

- [ ] Reset operator keys when canceling filter editing
  - Files: `src/music_minion/ui/blessed/events/keys/playlist_builder.py:212-225` (modify - add field reset)
  - Location: In `_handle_filter_editing_key()`, escape key handler
  - Add to replace() call: `filter_editor_operator_keys=[],`
  - Tests: Manual testing (Phase 6)
  - Acceptance: Operator keys cleared when pressing Escape

### Phase 6: Manual Integration Testing
- [ ] Test numeric operators work correctly
  - Verification Steps:
    1. Start music-minion: `uv run music-minion --dev`
    2. Navigate to manual playlist, press `b` for builder
    3. Press `f` to open filter editor
    4. Press `a` to add new filter
    5. Select `year`, then `<`, then enter `2024`
    6. Verify tracks with year < 2024 are displayed (should see hundreds)
    7. Test all numeric operators: `=`, `>`, `<`, `>=`, `<=`, `!=`
  - Acceptance: All numeric operators filter correctly

- [ ] Test text operators with multi-word display values
  - Verification Steps:
    1. Add filter with `genre` field
    2. Select `not equals` operator (multi-word display)
    3. Enter value `dubstep`
    4. Verify tracks without dubstep genre appear
    5. Test: `starts with`, `ends with`, `not equals`
  - Acceptance: Multi-word text operators work correctly

- [ ] Test AND filter logic with multiple filters
  - Verification Steps:
    1. Add filter 1: `year < 2024`
    2. Verify track count (should see hundreds)
    3. Add filter 2: `genre contains dubstep`
    4. Verify only tracks matching BOTH conditions appear
  - Acceptance: Multiple filters use AND logic correctly

- [ ] Test editing existing filters preserves operator
  - Verification Steps:
    1. Create filter with `year > 2020`
    2. Press `e` to edit the filter
    3. Verify `>` operator is selected in UI
    4. Change to `<` operator
    5. Save and verify filter uses `<` correctly
  - Acceptance: Editing filters shows correct operator and saves changes

- [ ] Test filter state persistence
  - Verification Steps:
    1. Add filters: `year < 2024` and `genre contains dubstep`
    2. Exit playlist builder with `q`
    3. Re-enter playlist builder with `b`
    4. Verify filters are restored and still work
  - Acceptance: Filters persist across builder sessions

## Acceptance Criteria
- ✅ Numeric operators (`<`, `>`, `=`, `>=`, `<=`, `!=`) filter tracks correctly
- ✅ Text operators with multi-word displays (`not equals`, `starts with`, etc.) work
- ✅ Multiple filters use AND logic (all conditions must match)
- ✅ Editing existing filters shows correct operator and saves changes
- ✅ Filter state persists across playlist builder sessions
- ✅ No Python type errors or runtime exceptions
- ✅ User's case (year < 2024 AND genre contains dubstep) returns expected results

## Files to Create/Modify

### Files to Modify
1. `src/music_minion/ui/blessed/state.py`
   - Line ~158: Add `filter_editor_operator_keys` field to `PlaylistBuilderState`
   - Lines 2217-2220: Extract operator keys alongside display values
   - Lines 2222-2228: Update operator index lookup to use keys
   - Lines 2230-2239: Store operator keys in state (step 0→1)
   - Lines 2241-2255: Save operator key instead of display value (step 1→2)
   - Lines 2112-2124: Reset keys on filter editor exit (toggle off)
   - Lines 2127-2139: Reset keys on filter editor enter (toggle on)
   - Lines 2325-2346: Reset keys when saving filter changes

2. `src/music_minion/ui/blessed/events/keys/playlist_builder.py`
   - Lines 212-225: Reset keys when canceling filter editing (Escape key)

### Files to Create
None (bug fix only)

## Dependencies

### Internal Dependencies
- No changes required to `BuilderFilter` dataclass (already stores operator correctly)
- No database schema changes required
- Filter matching logic in `_matches_builder_filter()` remains unchanged
- Render components for filter editor unchanged

### External Dependencies
None

### Operator Definitions Reference
**Location:** `src/music_minion/ui/blessed/state.py:1877-1884`

Numeric operators (tuples of `(key, display)`):
- `("equals", "=")` - Key stored: `"equals"`, UI shows: `"="`
- `("gt", ">")` - Key stored: `"gt"`, UI shows: `">"`
- `("lt", "<")` - Key stored: `"lt"`, UI shows: `"<"`
- `("gte", ">=")` - Key stored: `"gte"`, UI shows: `">="`
- `("lte", "<=")` - Key stored: `"lte"`, UI shows: `"<="`
- `("not_equals", "!=")` - Key stored: `"not_equals"`, UI shows: `"!="`

Text operators (tuples of `(key, display)`):
- `("contains", "contains")` - Key and display are same
- `("equals", "equals")` - Key and display are same
- `("not_equals", "not equals")` - Key: `"not_equals"`, Display: `"not equals"`
- `("starts_with", "starts with")` - Key: `"starts_with"`, Display: `"starts with"`
- `("ends_with", "ends with")` - Key: `"ends_with"`, Display: `"ends with"`

## Migration Notes

### Existing Filters
- Filters created before this bug was introduced: Already have correct operator keys stored
- Filters created with buggy filter editor: Have display values stored (e.g., `"<"` instead of `"lt"`)
  - These will fail to match until deleted and re-created after fix
  - No automatic migration planned (personal project, user can manually re-create)

### Backward Compatibility
- No backward compatibility required (personal project, no production users)
- User can delete all existing filters with `c` key and re-create after fix

## Testing Strategy

Since this is a personal project with no automated UI test suite:
1. Manual testing workflow (detailed in Phase 6 tasks)
2. Verify no Python exceptions in logs
3. Test all operator types: numeric and text
4. Test filter persistence across sessions
5. Test editing existing filters
6. Test AND logic with multiple filters

## Rollback Plan

If issues occur after implementation:
1. Revert all changes to `state.py` and `playlist_builder.py`
2. Remove `filter_editor_operator_keys` field from `PlaylistBuilderState`
3. User can still use text operators (keys match displays for most)
4. Numeric operators will return to buggy state (current behavior)

## Implementation Notes

**Why This Fix Works:**
- Operator tuples are defined as `(key, display)` in `BUILDER_NUMERIC_OPERATORS` and `BUILDER_TEXT_OPERATORS`
- Current code uses `op[1]` (display) for both UI and storage
- Fix uses `op[1]` (display) for UI options, `op[0]` (key) for storage
- Matching logic already expects keys, no changes needed there

**Edge Cases Handled:**
- Editing filter with invalid/missing operator key: Defaults to first option (index 0)
- Canceling edit: Operator keys properly reset
- Toggling filter mode on/off: Operator keys properly reset
- Multi-word display values: Correctly mapped to underscore keys (e.g., `"not equals"` → `"not_equals"`)
