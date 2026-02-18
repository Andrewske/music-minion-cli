---
task: 02-backend-schema-endpoint
status: pending
depends: [01-backend-analytics-functions]
files:
  - path: web/backend/schemas.py
    action: modify
  - path: web/backend/routers/playlists.py
    action: modify
---

# Extend PlaylistStatsResponse Schema & Endpoint

## Context
Wire up the new analytics functions to the API layer. Extend the schema to include leaderboard and pace data, then update the endpoint to populate these fields.

## Files to Modify/Create
- `web/backend/schemas.py` (modify)
- `web/backend/routers/playlists.py` (modify)

## Implementation Details

### 1. Update `PlaylistStatsResponse` in schemas.py

Add new fields:
```python
class PlaylistStatsResponse(BaseModel):
    playlist_name: str
    playlist_type: str
    basic: PlaylistBasicStats
    elo: PlaylistEloAnalysis
    quality: PlaylistQualityMetrics
    top_artists: list[ArtistStat]
    top_genres: list[GenreDistribution]
    # NEW FIELDS:
    avg_comparisons_per_day: float
    estimated_days_to_full_coverage: Optional[float] = None
```

### 2. Update `get_playlist_stats()` endpoint in playlists.py

```python
@router.get("/playlists/{playlist_id}/stats", response_model=PlaylistStatsResponse)
async def get_playlist_stats(playlist_id: int):
    # Existing analytics call
    analytics = get_playlist_analytics(playlist_id)

    # Add pace calculation
    from music_minion.domain.playlists.analytics import get_comparison_pace
    from music_minion.domain.rating.database import get_playlist_comparison_progress

    avg_per_day = get_comparison_pace(playlist_id)
    progress = get_playlist_comparison_progress(playlist_id)

    # Calculate estimated days - handle division by zero
    remaining_pairs = progress["total"] - progress["compared"]
    estimated_days = None
    if avg_per_day > 0 and remaining_pairs > 0:
        estimated_days = remaining_pairs / avg_per_day

    return PlaylistStatsResponse(
        # ... existing fields ...
        avg_comparisons_per_day=avg_per_day,
        estimated_days_to_full_coverage=estimated_days,
    )
```

## Verification
```bash
# Start backend
uv run uvicorn web.backend.main:app --reload &

# Test endpoint
curl http://localhost:8642/api/playlists/1/stats | jq '.avg_comparisons_per_day, .estimated_days_to_full_coverage'
```
