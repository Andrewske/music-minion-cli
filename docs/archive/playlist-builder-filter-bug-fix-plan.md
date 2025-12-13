# Playlist Builder Filter Editing Bug Fix Plan

## Problem Description
When editing the second filter in the playlist builder, it overwrites the first filter instead of modifying the second filter. This happens because the `filter_editor_selected` field is used for two different purposes:

1. Tracking which filter in the list is selected (when not editing)
2. Tracking selection within field/operator options (when editing)

During editing, `filter_editor_selected` gets overwritten with option indices, so when saving changes, the wrong filter index is used for replacement.

## Root Cause
In `_create_updated_filters()`, the code uses `builder.filter_editor_selected` as the index of the filter to replace, but this field contains the current selection within the editing options, not the target filter index.

## Solution
Add a new field `filter_editor_target_index` to `PlaylistBuilderState` to track which filter is being edited, separate from the `filter_editor_selected` field used for option navigation.

## Implementation Steps

### 1. Add filter_editor_target_index field
Add to `PlaylistBuilderState`:
```python
filter_editor_target_index: Optional[int] = None  # Index of filter being edited (None when adding new)
```

### 2. Update start_editing_filter()
Set `filter_editor_target_index` to the `filter_idx` parameter when starting to edit an existing filter.

### 3. Update _create_updated_filters()
Use `builder.filter_editor_target_index` instead of `builder.filter_editor_selected` when replacing existing filters.

### 4. Update _exit_filter_editor_with_changes()
Reset `filter_editor_target_index` to None when exiting the editor.

### 5. Update start_adding_filter()
Ensure `filter_editor_target_index` is None when adding new filters.

## Testing
- Create multiple filters in playlist builder
- Edit the second filter (not the first)
- Verify the second filter is modified, not the first
- Verify adding new filters still works
- Verify editing the first filter works correctly

## Files to Modify
- `src/music_minion/ui/blessed/state.py`: Add field, update functions
- Test with playlist builder UI

## Risk Assessment
Low risk - this is an isolated bug fix that only affects filter editing logic. The change adds a new field but doesn't modify existing behavior for non-editing scenarios.</content>
<parameter name="filePath">docs/playlist-builder-filter-bug-fix-plan.md