# Task 1: Dict-Based Command Dispatcher

## Goal
Replace 40-line elif chain in `_handle_internal_command()` with dict-based dispatch.

## Files
- `src/music_minion/ui/blessed/events/commands/executor.py`

## Context
Lines 159-403 contain a massive elif chain handling 20+ internal commands. Each branch follows the same pattern: extract data from `cmd.data`, call a handler, return tuple.

## Steps
1. Read `executor.py` lines 159-403
2. Create dict at module level:
   ```python
   INTERNAL_HANDLERS: dict[str, Callable] = {
       "play_track_from_viewer": _handle_play_track_from_viewer,
       "remove_track_from_playlist": _handle_remove_track,
       # ... etc
   }
   ```
3. Extract each elif branch into standalone function with signature `(ctx, ui_state, data) -> tuple[AppContext, UIState, bool]`
4. Replace elif chain with:
   ```python
   handler = INTERNAL_HANDLERS.get(cmd.action)
   if handler:
       return handler(ctx, ui_state, cmd.data)
   return ctx, add_history_line(ui_state, f"Unknown: {cmd.action}", "yellow"), False
   ```
5. Verify: `uv run python -m py_compile src/music_minion/ui/blessed/events/commands/executor.py`
6. Test: `uv run music-minion --dev` - try play, skip, palette commands

## Success Criteria
- All commands work identically
- elif chain eliminated (~200 lines reduced)
- Adding new commands = add dict entry + handler function
