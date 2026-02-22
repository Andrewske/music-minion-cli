---
task: 02-backend-api
status: done
depends: [01-database-migration]
files:
  - path: web/backend/routers/quicktag.py
    action: create
  - path: web/backend/main.py
    action: modify
---

# Backend API - Quick Tag Endpoints

## Context
REST API for the Quick Tag feature. Provides endpoints to fetch dimensions, submit votes, and retrieve vote summaries. Frontend will call these to power the sidebar voting UI.

## Files to Modify/Create
- web/backend/routers/quicktag.py (create)
- web/backend/main.py (modify)

## Implementation Details

### 1. Create Router (`web/backend/routers/quicktag.py`)

**Imports:**
```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from typing import Literal
```

**Pydantic Models:**
```python
class DimensionPair(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    id: str
    left_emoji: str
    right_emoji: str
    label: str
    description: str | None
    sort_order: int

class VoteRequest(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    track_id: int
    dimension_id: str
    vote: Literal[-1, 0, 1]

class TrackDimensionVote(BaseModel):
    """Single vote for a track-dimension pair."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    dimension_id: str
    vote: int  # -1, 0, or 1
    voted_at: str
```

**Endpoints:**

| Method | Path | Handler | Returns |
|--------|------|---------|---------|
| GET | `/dimensions` | Return all dimension_pairs ordered by sort_order | `list[DimensionPair]` |
| POST | `/vote` | Upsert vote (INSERT OR REPLACE) | `{"success": true}` |
| GET | `/tracks/{track_id}/votes` | Get all votes for a track | `list[TrackDimensionVote]` |

### 2. Register Router (`web/backend/main.py`)

Add import and registration:
```python
from routers import quicktag
app.include_router(quicktag.router, prefix="/api/quicktag", tags=["quicktag"])
```

## Verification
1. Start web backend: `music-minion --web`
2. Test endpoints:
   ```bash
   # Get dimensions
   curl http://localhost:8642/api/quicktag/dimensions | jq

   # Submit a vote (use a real track_id from your library)
   curl -X POST http://localhost:8642/api/quicktag/vote \
     -H "Content-Type: application/json" \
     -d '{"trackId": 1, "dimensionId": "filth", "vote": 1}'

   # Get summary
   curl http://localhost:8642/api/quicktag/tracks/1/summary | jq
   ```
3. Verify vote in database:
   ```bash
   sqlite3 ~/.local/share/music-minion/music_minion.db \
     "SELECT * FROM track_dimension_votes"
   ```
