# Memoized Selectors for Expensive Operations

## Problem

Expensive computations (search filtering, analytics formatting, comparison pair selection) recalculate on every render even when inputs haven't changed. This wastes CPU cycles in tight render loops.

## Solution

Add Redux-style memoized selectors that cache results based on input equality. Only recalculate when inputs actually change.

## Files to Create

- `src/music_minion/ui/blessed/state_selectors.py` (NEW)

## Implementation Steps

1. **Create MemoizedSelector class**
   - Cache last inputs and last result
   - Compare new inputs to cached inputs
   - Only call function if inputs changed
   - Return cached result if inputs identical

2. **Implement selectors for**:
   - Track filtering in search mode
   - Analytics line formatting
   - Comparison strategic pair selection
   - Any other O(n) operations in render path

3. **Use pattern**:
   ```python
   @MemoizedSelector
   def filter_search_tracks(query: str, tracks: list[dict]) -> list[dict]:
       # Expensive fuzzy matching
   ```

4. **Update call sites** to use selectors instead of direct computation

## Key Requirements

- Selector class must be functional (no shared state between instances)
- Use tuple comparison for input equality check
- Keep selectors as pure functions
- Add type hints for all parameters and returns

## Success Criteria

- No recalculation when inputs unchanged
- Search filtering remains responsive during typing
- Analytics viewer doesn't lag on updates
- All existing functionality works identically

## Testing

- Verify memoization by adding logging to expensive operations
- Confirm cache hits when inputs don't change
- Test with various input combinations
