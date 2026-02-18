---
task: 04-cleanup-dead-code
status: done
depends: [03-frontend-stats-modal]
files:
  - path: web/frontend/src/api/stats.ts
    action: delete
  - path: web/frontend/src/hooks/useStats.ts
    action: delete
  - path: web/backend/schemas.py
    action: modify
  - path: web/frontend/src/types/index.ts
    action: modify
---

# Remove Dead Global Stats Code

## Context
After unifying to playlist-only stats, remove the now-unused global stats API, hook, and types.

## Files to Delete
- `web/frontend/src/api/stats.ts`
- `web/frontend/src/hooks/useStats.ts`

## Files to Modify
- `web/backend/schemas.py` (modify) - remove `StatsResponse` class
- `web/frontend/src/types/index.ts` (modify) - remove `StatsResponse` interface

## Implementation Details

### 1. Delete frontend files
```bash
rm web/frontend/src/api/stats.ts
rm web/frontend/src/hooks/useStats.ts
```

### 2. Remove `StatsResponse` from schemas.py

Delete this class (keep `GenreStat` and `LeaderboardEntry` as they're reused):
```python
# DELETE THIS:
class StatsResponse(BaseModel):
    total_comparisons: int
    compared_tracks: int
    total_tracks: int
    coverage_percent: float
    average_comparisons_per_day: float
    estimated_days_to_coverage: Optional[float]
    prioritized_tracks: Optional[int] = None
    prioritized_coverage_percent: Optional[float] = None
    prioritized_estimated_days: Optional[float] = None
    top_genres: list[GenreStat]
    leaderboard: list[LeaderboardEntry]
```

### 3. Remove `StatsResponse` from types/index.ts

Delete this interface:
```typescript
// DELETE THIS:
export interface StatsResponse {
  total_comparisons: number;
  compared_tracks: number;
  total_tracks: number;
  coverage_percent: number;
  average_comparisons_per_day: number;
  estimated_days_to_coverage: number | null;
  prioritized_tracks: number | null;
  prioritized_coverage_percent: number | null;
  prioritized_estimated_days: number | null;
  top_genres: GenreStat[];
  leaderboard: LeaderboardEntry[];
}
```

## Verification
```bash
# Check no imports of deleted files
grep -r "from.*stats" web/frontend/src/ | grep -v node_modules
grep -r "useStats" web/frontend/src/ | grep -v node_modules

# Verify TypeScript compiles
cd web/frontend && npm run type-check

# Verify backend still imports
uv run python -c "from web.backend.schemas import PlaylistStatsResponse; print('OK')"
```
