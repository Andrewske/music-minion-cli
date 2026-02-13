# Track Selection Sync

## Files to Modify/Create
- `web/backend/routers/comparisons.py` (modify - add endpoint)
- `web/frontend/src/api/comparisons.ts` (modify - add function)
- Comparison UI component (modify - call on track select)

## Implementation Details

### Part 1: Backend Endpoint

```python
# web/backend/routers/comparisons.py - ADD
from pydantic import BaseModel
from ..sync_manager import sync_manager

class TrackSelectionRequest(BaseModel):
    track_id: int | str  # int from frontend, "track_a"/"track_b" from CLI
    is_playing: bool


@router.post("/comparisons/select-track")
async def select_track(request: TrackSelectionRequest):
    """Broadcast track selection to all clients."""
    track_id = request.track_id

    # Resolve CLI aliases to actual track IDs
    if isinstance(track_id, str):
        current = sync_manager.current_comparison
        if not current or not current.get("pair"):
            return {"status": "error", "message": "No active comparison"}
        if track_id == "track_a":
            track_id = current["pair"]["track_a"]["id"]
            track_info = current["pair"]["track_a"]
        elif track_id == "track_b":
            track_id = current["pair"]["track_b"]
            track_info = current["pair"]["track_b"]
        else:
            return {"status": "error", "message": f"Unknown track alias: {track_id}"}
    else:
        # Look up track info from current comparison pair
        current = sync_manager.current_comparison
        if current and current.get("pair"):
            pair = current["pair"]
            if pair["track_a"]["id"] == track_id:
                track_info = pair["track_a"]
            elif pair["track_b"]["id"] == track_id:
                track_info = pair["track_b"]
            else:
                track_info = {"id": track_id}  # Fallback
        else:
            track_info = {"id": track_id}

    # Broadcast full track object (not just ID)
    await sync_manager.broadcast("comparison:track_selected", {
        "track": track_info,
        "isPlaying": request.is_playing,
    })
    return {"status": "ok"}
```

### Part 2: Frontend API Function

```typescript
// web/frontend/src/api/comparisons.ts - ADD
export async function selectTrack(trackId: number, isPlaying: boolean): Promise<void> {
  await fetch('/api/comparisons/select-track', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ track_id: trackId, is_playing: isPlaying }),
  });
}
```

### Part 3: Call from Comparison UI

Find where `selectAndPlay(track)` is called in the comparison component. Add:

```typescript
import { selectTrack } from '../api/comparisons';

// After selectAndPlay(track):
selectTrack(track.id, true);
```

**Note:** Echo prevention is NOT needed. `setCurrentTrack()` and `selectAndPlay()` are idempotent - calling them twice with the same track has no visible effect. The slight redundancy of the local action echoing back is harmless.

## Acceptance Criteria

1. Open two browser tabs with comparison mode
2. Click Track B in tab 1
3. Tab 2 immediately shows Track B selected
4. No infinite loops or echo effects

## Dependencies

- Task 01 (Backend WebSocket Core)
- Task 03 (Frontend Sync Hook)

## Commits

```bash
git add web/backend/routers/comparisons.py web/frontend/src/api/comparisons.ts
git commit -m "feat(sync): broadcast track selection between devices"
```
