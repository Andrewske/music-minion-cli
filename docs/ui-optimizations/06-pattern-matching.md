# Use Pattern Matching for Mode Dispatch

## Problem

Mode detection in keyboard.py uses nested if/elif chains (10+ branches). This is verbose and harder to extend. Python 3.10+ offers pattern matching for cleaner dispatch.

## Solution

Replace nested if/elif with match/case statements for explicit, exhaustive mode routing. Completes after keyboard split for maximum benefit.

## Files to Modify

- `src/music_minion/ui/blessed/events/keyboard.py`

## Implementation Steps

1. **Create detect_mode() helper**:
   ```python
   def detect_mode(state: UIState) -> str:
       # Pure function - returns mode name as string
       if state.comparison.active:
           return "comparison"
       elif state.rating_history_visible:
           return "rating_history"
       # ... explicit checks
       return "normal"
   ```

2. **Replace handle_key() dispatch** with match statement:
   ```python
   def handle_key(state: UIState, key: Keystroke) -> tuple[UIState, Optional[InternalCommand]]:
       event = parse_key(key)
       mode = detect_mode(state)

       match mode:
           case "comparison":
               return handle_comparison_key(key, state)
           case "rating_history":
               return handle_rating_history_key(state, event)
           case "wizard":
               return handle_wizard_key(state, event)
           case "palette":
               return handle_palette_key(state, event)
           case _:
               return handle_normal_key(state, event)
   ```

3. **Benefits of match statement**:
   - Clearer intent (explicit mode names)
   - Exhaustiveness checking (catch missing cases)
   - Easier to extend (add new modes)
   - Better performance (compiler optimizations)

4. **Check Python version**: Ensure project uses Python 3.10+

## Key Requirements

- Maintain functional paradigm
- Keep detect_mode() as pure function
- All mode handlers remain pure functions
- No behavioral changes
- Explicit mode strings for clarity

## Success Criteria

- Cleaner, more readable dispatch logic
- All keyboard interactions work identically
- Easier to add new modes in future
- No test failures

## Testing

- Test all keyboard shortcuts in each mode
- Verify mode detection is accurate
- Test mode transitions
- Run full test suite

## Notes

- This optimization has the least impact on maintainability
- Implement after keyboard split for maximum benefit
- Can be skipped if Python version < 3.10
