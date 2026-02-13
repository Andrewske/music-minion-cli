# CLI/IPC Integration - Context-Aware Command Routing

## Files to Modify
- `src/music_minion/context.py` (modify - add fields)
- `src/music_minion/ui/blessed/events/commands/executor.py` (modify - update handlers)

## Implementation Details

Enable `web-winner` and `web-archive` CLI commands to work context-aware based on active web mode (comparison vs builder).

### 1. Update AppContext (`src/music_minion/context.py`)

Add two new fields to the `AppContext` dataclass:

```python
@dataclass
class AppContext:
    # ... existing fields ...
    active_web_mode: Optional[str] = None  # 'comparison' | 'builder'
    active_builder_playlist_id: Optional[int] = None
```

Add helper method after existing `with_*()` methods:

```python
def with_web_mode(self, mode: Optional[str], playlist_id: Optional[int] = None) -> "AppContext":
    """Return new context with updated web mode.

    Args:
        mode: Web mode ('comparison', 'builder', or None)
        playlist_id: Active builder playlist ID (required if mode='builder')

    Returns:
        New AppContext with updated web mode fields
    """
    return AppContext(
        config=self.config,
        music_tracks=self.music_tracks,
        player_state=self.player_state,
        provider_states=self.provider_states,
        spotify_player=self.spotify_player,
        console=self.console,
        ui_action=self.ui_action,
        ui_mode=self.ui_mode,
        update_ui_state=self.update_ui_state,
        active_web_mode=mode,
        active_builder_playlist_id=playlist_id,
    )
```

### 2. Update Command Executor (`src/music_minion/ui/blessed/events/commands/executor.py`)

Locate the existing `_handle_web_winner_cmd()` and `_handle_web_archive_cmd()` functions and update them to be context-aware:

```python
def _handle_web_winner_cmd(ctx: AppContext, ui_state, data):
    """Route web-winner command based on active web mode."""
    from music_minion.core.output import log

    if ctx.active_web_mode == "builder":
        # Builder mode: Add track to playlist
        # Broadcast message to web clients via WebSocket
        message = {
            "type": "builder:add",
            "playlist_id": ctx.active_builder_playlist_id,
            "timestamp": datetime.now().isoformat()
        }
        # TODO: Broadcast via IPC server's web_broadcast_queue
        log("✅ Track added to playlist", level="info")

    elif ctx.active_web_mode == "comparison":
        # Existing comparison logic (preserve as-is)
        # ... existing code ...
        pass

    else:
        log("⚠️  No active web mode set", level="warning")

    return ctx, ui_state, False


def _handle_web_archive_cmd(ctx: AppContext, ui_state, data):
    """Route web-archive command based on active web mode."""
    from music_minion.core.output import log

    if ctx.active_web_mode == "builder":
        # Builder mode: Skip track (add to skipped list)
        message = {
            "type": "builder:skip",
            "playlist_id": ctx.active_builder_playlist_id,
            "timestamp": datetime.now().isoformat()
        }
        # TODO: Broadcast via IPC server's web_broadcast_queue
        log("⏭  Track skipped", level="info")

    elif ctx.active_web_mode == "comparison":
        # Existing comparison logic (preserve as-is)
        # ... existing code ...
        pass

    else:
        log("⚠️  No active web mode set", level="warning")

    return ctx, ui_state, False
```

### 3. WebSocket Message Format Documentation

Document the WebSocket message format in `src/music_minion/ipc/server.py` (add as comment):

```python
# Builder WebSocket Messages:
#
# Add track:
# {
#   "type": "builder:add",
#   "playlist_id": 123,
#   "timestamp": "2026-01-19T12:00:00Z"
# }
#
# Skip track:
# {
#   "type": "builder:skip",
#   "playlist_id": 123,
#   "timestamp": "2026-01-19T12:00:00Z"
# }
```

### Broadcasting Implementation

The IPC server already has `web_broadcast_queue` for sending messages to web clients. The frontend will listen for these WebSocket messages and trigger the appropriate API calls.

**Message Flow:**
1. User presses keyboard shortcut (mapped to `music-minion-cli web-winner`)
2. CLI sends IPC message to blessed UI
3. Executor routes based on `ctx.active_web_mode`
4. Message broadcasted to WebSocket clients
5. Frontend receives message and calls builder API

## Acceptance Criteria

1. `AppContext` has two new fields: `active_web_mode` and `active_builder_playlist_id`
2. `with_web_mode()` helper method added
3. `_handle_web_winner_cmd()` routes based on mode
4. `_handle_web_archive_cmd()` routes based on mode
5. Existing comparison mode logic preserved (no breaking changes)
6. WebSocket message format documented
7. Log messages provide clear feedback

## Dependencies
- Task 01: Database migration
- Task 02: Domain logic
- Task 03: Backend API routes

## Testing

Manual testing:
1. Start blessed UI: `uv run music-minion --web`
2. Open web frontend at `http://localhost:5173/playlist-builder`
3. Frontend sets `active_web_mode = 'builder'` via context update
4. Press keyboard shortcut for `web-winner`
5. Verify log shows "✅ Track added to playlist"
6. Verify WebSocket message sent to frontend
7. Frontend triggers API call to add track

Integration test:
```python
def test_web_winner_routes_to_builder():
    """Test web-winner command routes to builder when active."""
    ctx = AppContext.create(config)
    ctx = ctx.with_web_mode('builder', playlist_id=1)

    ctx, ui_state, _ = _handle_web_winner_cmd(ctx, ui_state, {})

    # Verify broadcast message sent
    # Verify log message
```
