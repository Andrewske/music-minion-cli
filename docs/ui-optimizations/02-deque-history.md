# Replace History List with Deque

## Problem

Command history uses a list with manual trimming logic when it exceeds MAX_COMMAND_HISTORY (1000 items). This requires explicit size checks and slicing.

## Solution

Use `collections.deque` with `maxlen=1000` for automatic eviction of oldest items. Simplifies code and guarantees memory bounds.

## Files to Modify

- `src/music_minion/ui/blessed/state.py`

## Implementation Steps

1. **Import deque**:
   ```python
   from collections import deque
   ```

2. **Update UIState field**:
   - Find `history: list[tuple[str, str]]` field
   - Change to `history: deque = field(default_factory=lambda: deque(maxlen=1000))`

3. **Update add_history_line function**:
   - Remove manual trimming logic (`if len(new_history) > MAX_COMMAND_HISTORY`)
   - Use `new_history.append()` (auto-evicts oldest)
   - Keep immutable pattern: `new_history = state.history.copy()`

4. **Verify history rendering**:
   - Deque supports slicing: `history[-10:]` works
   - All existing history access patterns remain compatible

## Key Requirements

- Maintain immutability (copy deque before appending)
- Keep maxlen=1000 (current MAX_COMMAND_HISTORY)
- All history access patterns must work identically
- No changes to render functions needed

## Success Criteria

- History automatically evicts oldest when full
- No manual size checking required
- All existing history functionality works
- Command palette history scrolling works

## Testing

- Add 1001+ history items, verify oldest removed
- Test history scrolling in UI
- Verify history rendering in dashboard
