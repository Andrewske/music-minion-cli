# Backend Consistency Check

## Files to Review/Modify
- `src/music_minion/domain/playback/player.py` (review, possibly modify)
- `src/music_minion/commands/playback.py` (review, possibly modify)

## Implementation Details

The backend already separates `current_track` and `is_playing` in `PlayerState`. Verify this is working correctly and consider if we need a "load without play" pathway.

### Review PlayerState

```python
class PlayerState(NamedTuple):
    current_track: Optional[str] = None
    current_track_id: Optional[int] = None
    is_playing: bool = False  # Already separated!
    # ...
```

### Check play_file() in player.py

Currently sets `is_playing=True` after loading. For consistency with the new frontend model (load paused), evaluate if this needs to change:

```python
# Current behavior in play_file():
updated_state = state._replace(
    current_track=local_path,
    current_track_id=track_id,
    is_playing=True,  # Auto-plays
    # ...
)
```

### Decision Point

Two options:
1. **Keep backend auto-play**: The web frontend controls its own playback state independently. Backend commands are for the CLI/blessed UI which may have different behavior.
2. **Add load_file() without play**: Create separate `load_file()` that sets `is_playing=False`, keep `play_file()` as-is.

**Recommendation**: Keep backend as-is for now. The web frontend has its own state management through the Zustand store. The backend `is_playing` is primarily for the blessed CLI interface, not the web UI.

### Verify No Auto-Play on Web Session Start

When web frontend starts a comparison session, it should:
1. Call API to get comparison pair
2. Frontend store sets `currentTrack` but `isPlaying: false`
3. No backend play command is issued until user clicks play

Check the session start flow to ensure this is true.

## Acceptance Criteria
- [ ] Reviewed `PlayerState` separation - confirmed already correct
- [ ] Documented decision on backend play behavior
- [ ] Verified web session start doesn't trigger backend auto-play
- [ ] If changes made: backend tests still pass

## Dependencies
- None (this is a verification task, can run in parallel with frontend work)
