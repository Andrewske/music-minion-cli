# Backend Broadcast Integration

## Files to Modify/Create
- `web/backend/routers/comparisons.py` (modify)
- `web/backend/routers/radio.py` (modify)

## Implementation Details

### Part 1: Broadcast on Comparison Verdict

First, identify the verdict endpoint in `comparisons.py` (`record_comparison_result`). Then add broadcast after recording:

```python
# web/backend/routers/comparisons.py - ADD import at top
from ..sync_manager import sync_manager

# In record_comparison_result, BEFORE the return statement, add:
    # Update stored state for reconnecting clients
    sync_manager.set_comparison_state(
        next_pair.dict(),
        prefetched_pair.dict() if prefetched_pair else None
    )

    # Broadcast to all connected clients
    await sync_manager.broadcast("comparison:advanced", {
        "pair": next_pair.dict(),
        "prefetched": prefetched_pair.dict() if prefetched_pair else None,
    })

    return RecordComparisonResponse(...)
```

**Note:** The endpoint is already `async def record_comparison_result(...)` so no change needed there.

### Part 2: Broadcast on Radio Track Start

Find the track-started endpoint (Liquidsoap callback) in `radio.py`:

```python
# web/backend/routers/radio.py - ADD import at top
from ..sync_manager import sync_manager

# In the track_started endpoint, after record_now_playing() succeeds, add:
    # Build full NowPlaying response for broadcast
    now_playing_data = {
        "track": _track_to_response(track).dict(),
        "position_ms": 0,
        "station_id": station.id,
        "station_name": station.name,
        "source_type": source_type,
        "upcoming": [],  # Could populate if needed
    }

    # Update stored state for reconnecting clients
    sync_manager.set_radio_state(now_playing_data)

    # Broadcast to all connected clients
    await sync_manager.broadcast("radio:now_playing", now_playing_data)
```

**Note:** The endpoint needs to become `async def track_started(...)` to use `await`. Also need to look up the Track object to call `_track_to_response()`.

### Test (Optional)

```python
# Add to web/backend/tests/test_sync_manager.py
@pytest.mark.asyncio
async def test_verdict_broadcasts_to_connected_clients():
    from ..main import app
    from ..sync_manager import sync_manager
    from fastapi.testclient import TestClient
    from unittest.mock import AsyncMock, patch

    client = TestClient(app)
    mock_ws = AsyncMock()
    sync_manager.connections = [mock_ws]

    with patch('web.backend.routers.comparisons.record_comparison') as mock_record:
        mock_record.return_value = {"next_pair": {"track_a": {}, "track_b": {}}}
        response = client.post("/api/comparisons/verdict", json={
            "session_id": "test",
            "track_a_id": 1,
            "track_b_id": 2,
            "winner_id": 1,
        })

    assert mock_ws.send_json.called
    call_arg = mock_ws.send_json.call_args[0][0]
    assert call_arg["type"] == "comparison:advanced"
```

## Acceptance Criteria

1. Start backend with WebSocket endpoint from Task 01
2. Connect a WebSocket client to `/ws/sync`
3. Record a verdict via REST API
4. WebSocket client receives `comparison:advanced` message
5. Trigger radio track start (if Liquidsoap available)
6. WebSocket client receives `radio:now_playing` message

## Dependencies

- Task 01 (Backend WebSocket Core) must be complete

## Commits

```bash
git add web/backend/routers/comparisons.py
git commit -m "feat(sync): broadcast comparison:advanced on verdict"

git add web/backend/routers/radio.py
git commit -m "feat(sync): broadcast radio:now_playing on track start"
```
