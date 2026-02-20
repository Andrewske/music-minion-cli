---
task: 05-history-page-update
status: done
depends: [04-frontend-api-update]
files:
  - path: web/frontend/src/components/HistoryPage.tsx
    action: modify
---

# Update History Page Component

## Context
Remove station filtering UI and update to use new simplified API. Keep date filters, pagination, stats, top tracks, and timeline view.

## Files to Modify/Create
- web/frontend/src/components/HistoryPage.tsx (modify)

## Implementation Details

### Remove station-related state and UI:
- Delete `selectedStation` state
- Delete station dropdown/filter component
- Remove station queries
- Remove station name display in entries

### Update queries to use new API:

```typescript
// Replace station-filtered queries with global queries
const { data: historyData, fetchNextPage, hasNextPage, isLoading } =
  useInfiniteQuery({
    queryKey: ['history', dateRange],
    queryFn: ({ pageParam = 0 }) => getHistory({
      limit: 50,
      offset: pageParam,
      startDate: dateRange.start,
      endDate: dateRange.end
    }),
    getNextPageParam: (lastPage, pages) =>
      lastPage.length === 50 ? pages.length * 50 : undefined
  });

const { data: stats } = useQuery({
  queryKey: ['history-stats', dateRange],
  queryFn: () => getStats(dateRange.days)
});

const { data: topTracks } = useQuery({
  queryKey: ['top-tracks', dateRange],
  queryFn: () => getTopTracks(10, dateRange.days)
});
```

### Update imports:
```typescript
// Change from:
import { getHistory, getStations, getStationStats, getTopTracks } from '../api/radio';
// To:
import { getHistory, getStats, getTopTracks } from '../api/history';
```

### Update stats display:
Show global stats (no station selection needed):
- Total plays (all time or filtered range)
- Hours listened (from `total_minutes` - actual listening time)
- Unique tracks

### Update timeline entry rendering:
- Remove station name from entries
- Show: track title, artist, timestamp, duration listened
- Format duration: `duration_ms / 1000` → seconds, then format as "2:34"
- Show end_reason as subtle indicator (skip icon vs checkmark for completed)

### Date range filter (keep existing):
- Last 7 days
- Last 30 days
- All time

## Verification
1. Navigate to `/history` in browser
2. Page should load without errors
3. Stats cards show global totals
4. Timeline shows recent plays with duration
5. Top tracks section shows most played
6. Date filters work correctly
7. "Load More" pagination works
