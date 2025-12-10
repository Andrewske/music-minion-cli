# Web Comparison Stats Feature Implementation Plan

## Overview
Add a stats view to the web comparison UI showing comparison metrics, coverage statistics, top genres by ELO rating, and a track leaderboard.

## Architecture Decisions
- **Single endpoint**: One `GET /api/stats` endpoint returns all stats to minimize frontend round-trips
- **Tab navigation**: Separate stats page with tab nav (vs modal) - provides room for charts and leaderboards
- **Coverage target**: 5 comparisons per track considered "good coverage"
- **Reuse existing functions**: Leverage `get_ratings_coverage()` and `get_leaderboard()` from domain layer
- **React Query for fetching**: 30s staleTime, 60s auto-refetch for live updates

## Implementation Tasks

### Phase 1: Backend Schemas
- [x] Add Pydantic models to schemas.py
  - Files: `web/backend/schemas.py` (modify)
  - Tests: Not required (Pydantic validates automatically)
  - Acceptance: Models match TypeScript interfaces exactly
  - Details:
    ```python
    class GenreStat(BaseModel):
        genre: str
        track_count: int
        average_rating: float
        total_comparisons: int

    class LeaderboardEntry(BaseModel):
        track_id: int
        title: str
        artist: str
        rating: float
        comparison_count: int
        wins: int
        losses: int

    class StatsResponse(BaseModel):
        total_comparisons: int
        compared_tracks: int
        total_tracks: int
        coverage_percent: float
        average_comparisons_per_day: float
        estimated_days_to_coverage: Optional[float]
        top_genres: list[GenreStat]
        leaderboard: list[LeaderboardEntry]
    ```

### Phase 2: Backend Stats Router
- [x] Create stats router with GET /api/stats endpoint
  - Files: `web/backend/routers/stats.py` (new)
  - Tests: `web/backend/tests/test_stats.py` (new)
  - Acceptance: Returns valid StatsResponse JSON
  - Dependencies: Phase 1 complete
  - Details:
    - Reuse `get_ratings_coverage()` from `music_minion.domain.rating.database`
    - Reuse `get_leaderboard(limit=20, min_comparisons=5)` from same module
    - Implement helper functions:
      - `_calculate_avg_comparisons_per_day(days=7)`: Query comparison_history for last 7 days
      - `_estimate_coverage_time(coverage, avg_per_day, target=5)`: Calculate days until all tracks have 5+ comparisons
      - `_get_genre_stats(limit=10)`: GROUP BY genre with AVG(rating), filter genres with 3+ tracks

- [x] Register stats router in main.py
  - Files: `web/backend/main.py` (modify)
  - Tests: Covered by integration test
  - Acceptance: `/api/stats` endpoint accessible
  - Dependencies: Stats router created

### Phase 3: Frontend Types and API
- [x] Add TypeScript interfaces for stats
  - Files: `web/frontend/src/types/index.ts` (modify)
  - Tests: TypeScript compiler validates
  - Acceptance: Types match Pydantic schemas exactly
  - Details:
    ```typescript
    export interface GenreStat {
      genre: string;
      track_count: number;
      average_rating: number;
      total_comparisons: number;
    }

    export interface LeaderboardEntry {
      track_id: number;
      title: string;
      artist: string;
      rating: number;
      comparison_count: number;
      wins: number;
      losses: number;
    }

    export interface StatsResponse {
      total_comparisons: number;
      compared_tracks: number;
      total_tracks: number;
      coverage_percent: number;
      average_comparisons_per_day: number;
      estimated_days_to_coverage: number | null;
      top_genres: GenreStat[];
      leaderboard: LeaderboardEntry[];
    }
    ```

- [x] Create stats API client function
  - Files: `web/frontend/src/api/stats.ts` (new)
  - Tests: Not required (simple fetch wrapper)
  - Acceptance: Correctly typed API call
  - Details:
    ```typescript
    import { apiRequest } from './client';
    import type { StatsResponse } from '../types';

    export async function getStats(): Promise<StatsResponse> {
      return apiRequest<StatsResponse>('/stats');
    }
    ```

- [x] Create useStats React Query hook
  - Files: `web/frontend/src/hooks/useStats.ts` (new)
  - Tests: Not required (thin wrapper)
  - Acceptance: Returns query result with proper typing
  - Details:
    ```typescript
    import { useQuery } from '@tanstack/react-query';
    import { getStats } from '../api/stats';

    export function useStats() {
      return useQuery({
        queryKey: ['stats'],
        queryFn: getStats,
        staleTime: 30 * 1000,
        refetchInterval: 60 * 1000,
      });
    }
    ```

### Phase 4: Frontend Components
- [x] Create StatCard component
  - Files: `web/frontend/src/components/StatCard.tsx` (new)
  - Tests: Not required (presentational)
  - Acceptance: Renders metric with icon, value, subtitle, label
  - Details: Tailwind styled card with emoji icon, large value text, optional subtitle

- [x] Create GenreChart component
  - Files: `web/frontend/src/components/GenreChart.tsx` (new)
  - Tests: Not required (presentational)
  - Acceptance: Horizontal bar chart showing genre rankings
  - Details: Pure CSS bars (no chart library), gradient fill, rating value displayed

- [x] Create Leaderboard component
  - Files: `web/frontend/src/components/Leaderboard.tsx` (new)
  - Tests: Not required (presentational)
  - Acceptance: Table with rank, title/artist, rating, W/L columns
  - Details: Tailwind table with hover states, truncated text, colored W/L numbers

- [x] Create StatsView main component
  - Files: `web/frontend/src/components/StatsView.tsx` (new)
  - Tests: Not required (composition)
  - Acceptance: Assembles all stat components with loading/error states
  - Dependencies: StatCard, GenreChart, Leaderboard, useStats hook
  - Details:
    - Loading skeleton state
    - Error state with retry
    - 4-column grid for stat cards (responsive)
    - Genre chart section
    - Leaderboard section

### Phase 5: Navigation Integration
- [x] Add tab navigation to App.tsx
  - Files: `web/frontend/src/App.tsx` (modify)
  - Tests: Manual testing
  - Acceptance: Can switch between Compare and Stats views
  - Dependencies: StatsView component
  - Details:
    - Add `useState<'compare' | 'stats'>` for current view
    - Add sticky nav header with tab buttons
    - Conditionally render ComparisonView or StatsView

## Acceptance Criteria
- [x] `GET /api/stats` returns valid JSON with all required fields
- [x] Stats view displays all 4 summary metrics
- [x] Genre chart shows top 10 genres by average rating
- [x] Leaderboard shows top 20 tracks
- [x] Tab navigation switches between Compare and Stats views
- [x] Stats auto-refresh every 60 seconds
- [x] No TypeScript errors
- [x] Backend tests pass

## Files to Create
| File | Purpose |
|------|---------|
| `web/backend/routers/stats.py` | Stats API endpoint |
| `web/backend/tests/test_stats.py` | Backend tests |
| `web/frontend/src/api/stats.ts` | API client function |
| `web/frontend/src/hooks/useStats.ts` | React Query hook |
| `web/frontend/src/components/StatCard.tsx` | Metric card |
| `web/frontend/src/components/GenreChart.tsx` | Genre bar chart |
| `web/frontend/src/components/Leaderboard.tsx` | Top tracks table |
| `web/frontend/src/components/StatsView.tsx` | Main stats page |

## Files to Modify
| File | Changes |
|------|---------|
| `web/backend/schemas.py` | Add GenreStat, LeaderboardEntry, StatsResponse |
| `web/backend/main.py` | Register stats router |
| `web/frontend/src/types/index.ts` | Add TypeScript interfaces |
| `web/frontend/src/App.tsx` | Add tab navigation |

## Dependencies
- Existing: `music_minion.domain.rating.database` functions (get_ratings_coverage, get_leaderboard)
- Existing: `web/frontend/src/api/client.ts` (apiRequest helper)
- Existing: @tanstack/react-query (already installed)
- No new external dependencies required

## SQL Queries Reference

### Average comparisons per day (7 days)
```sql
SELECT COUNT(*) / 7.0 as avg_per_day
FROM comparison_history
WHERE timestamp >= datetime('now', '-7 days')
```

### Genre stats
```sql
SELECT
    t.genre,
    COUNT(*) as track_count,
    AVG(e.rating) as average_rating,
    SUM(e.comparison_count) as total_comparisons
FROM tracks t
JOIN elo_ratings e ON t.id = e.track_id
WHERE t.genre IS NOT NULL AND t.genre != ''
  AND e.comparison_count >= 5
GROUP BY t.genre
HAVING COUNT(*) >= 3
ORDER BY average_rating DESC
LIMIT 10
```

### Coverage time estimation
```sql
SELECT SUM(5 - COALESCE(e.comparison_count, 0)) as comparisons_needed
FROM tracks t
LEFT JOIN elo_ratings e ON t.id = e.track_id
WHERE COALESCE(e.comparison_count, 0) < 5
```
Then: `days = comparisons_needed / 2 / avg_per_day` (each comparison covers 2 tracks)
