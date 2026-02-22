---
task: 01-backend-emoji-sync
status: done
depends: []
files:
  - path: web/backend/routers/quicktag.py
    action: modify
  - path: web/frontend/src/hooks/useSyncWebSocket.ts
    action: modify
---

# Backend: Sync Quick Tag Votes to track_emojis

## Context
Quick Tag votes are stored in `track_dimension_votes` but TrackCard displays emojis from `track_emojis`. This task bridges the gap by writing the winning emoji to `track_emojis` when a vote is recorded, and returning the updated emoji list to the frontend.

## Files to Modify/Create
- web/backend/routers/quicktag.py (modify)

## Implementation Details

Modify `submit_vote()` endpoint to:

1. **Look up dimension emojis**: Query `dimension_pairs` table to get `left_emoji` and `right_emoji` for the voted dimension

2. **Record the vote** (existing logic - keep as-is)

3. **Sync to track_emojis based on vote value**:
   - If vote is -1: winning = left_emoji, losing = right_emoji
   - If vote is +1: winning = right_emoji, losing = left_emoji
   - If vote is 0 (skip): remove both dimension emojis from track

4. **Update track_emojis**:
   - Delete the losing emoji if present
   - Insert the winning emoji (INSERT OR IGNORE to avoid duplicates)
   - For skip: delete both emojis

5. **Return updated emojis**: Use `batch_fetch_track_emojis()` from `queries/emojis.py` to get current emojis for the track and include in response

**Add imports at top of file:**
```python
from fastapi import APIRouter, HTTPException
from ..queries.emojis import batch_fetch_track_emojis
from ..sync_manager import sync_manager
```

**Add response model after existing models:**
```python
class VoteResponse(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    success: bool
    emojis: list[str]
```

**Replace submit_vote function:**
```python
@router.post("/vote", response_model=VoteResponse)
async def submit_vote(request: VoteRequest) -> VoteResponse:
    with get_db_connection() as conn:
        # 1. Get dimension emojis (with validation)
        dim = conn.execute(
            "SELECT left_emoji, right_emoji FROM dimension_pairs WHERE id = ?",
            (request.dimension_id,)
        ).fetchone()

        if not dim:
            raise HTTPException(status_code=404, detail=f"Dimension '{request.dimension_id}' not found")

        # 2. Record vote (existing)
        conn.execute(
            "INSERT OR REPLACE INTO track_dimension_votes (track_id, dimension_id, vote, voted_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (request.track_id, request.dimension_id, request.vote),
        )

        # 3. Update track_emojis based on vote
        if request.vote != 0:
            winning_emoji = dim["left_emoji"] if request.vote == -1 else dim["right_emoji"]
            losing_emoji = dim["right_emoji"] if request.vote == -1 else dim["left_emoji"]

            conn.execute(
                "DELETE FROM track_emojis WHERE track_id = ? AND emoji_id = ?",
                (request.track_id, losing_emoji)
            )
            conn.execute(
                "INSERT OR IGNORE INTO track_emojis (track_id, emoji_id) VALUES (?, ?)",
                (request.track_id, winning_emoji)
            )
        else:
            conn.execute(
                "DELETE FROM track_emojis WHERE track_id = ? AND emoji_id IN (?, ?)",
                (request.track_id, dim["left_emoji"], dim["right_emoji"])
            )

        conn.commit()

        # 4. Get updated emojis
        emojis = batch_fetch_track_emojis([request.track_id], conn)
        emoji_list = emojis.get(request.track_id, [])

    # 5. Broadcast update via WebSocket (outside db context)
    await sync_manager.broadcast("track:emojis_updated", {
        "track_id": request.track_id,
        "emojis": emoji_list,
    })

    return VoteResponse(success=True, emojis=emoji_list)
```

**Note**: `get_db_connection()` already sets `conn.row_factory = sqlite3.Row`.

## Verification

1. Start backend: `cd web/backend && uv run uvicorn main:app --reload`
2. Use curl to test vote endpoint:
   ```bash
   # Vote for left emoji (should add that emoji to track_emojis)
   curl -X POST http://localhost:8642/api/quicktag/vote \
     -H "Content-Type: application/json" \
     -d '{"trackId": 1, "dimensionId": "energy", "vote": -1}'

   # Response should include "emojis" array with the voted emoji
   ```
3. Query database to verify emoji was added:
   ```bash
   sqlite3 ~/.local/share/music-minion/tracks.db \
     "SELECT * FROM track_emojis WHERE track_id = 1"
   ```
