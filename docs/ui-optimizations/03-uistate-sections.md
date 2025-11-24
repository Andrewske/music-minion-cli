# Add Section Comments to UIState

## Problem

UIState has 90+ fields in a single dataclass, making it difficult to scan and find related fields. Fields are logically grouped (palette_*, wizard_*, track_viewer_*) but not visually separated.

## Solution

Add section header comments to visually group related fields. Zero code changes, pure documentation improvement.

## Files to Modify

- `src/music_minion/ui/blessed/state.py`

## Implementation Steps

1. **Identify logical groups** by field prefixes:
   - Command history (history, history_scroll)
   - Command palette (palette_*)
   - Wizard (wizard_*)
   - Track viewer (track_viewer_*)
   - Search (search_*)
   - Analytics viewer (analytics_*)
   - Metadata editor (editor_*)
   - Comparison mode (comparison)
   - Rating history (rating_history_*)
   - Feedback messages (feedback_*)
   - Input (input_text, cursor_pos, command_history)
   - Dashboard cache (track_metadata, playlist_info, etc.)

2. **Add section headers**:
   ```python
   # ========================================
   # COMMAND PALETTE
   # ========================================
   palette_visible: bool = False
   palette_selected: int = 0
   # ...
   ```

3. **Use consistent formatting**:
   - Same header style for all sections
   - Clear visual separation
   - Alphabetical or logical ordering within sections

## Key Requirements

- No code changes (comments only)
- Maintain existing field order (minimize diff)
- Clear, descriptive section names
- Consistent header formatting

## Success Criteria

- Easier to navigate UIState definition
- Related fields visually grouped
- No functionality changes
- No test failures

## Testing

- Run full test suite
- Verify no behavior changes
- Import statement still works
