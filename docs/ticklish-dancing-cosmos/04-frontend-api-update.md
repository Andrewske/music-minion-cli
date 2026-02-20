---
task: 04-frontend-api-update
status: done
depends: [02-history-router]
files:
  - path: web/frontend/src/api/radio.ts
    action: modify
---

# Update Frontend API Client

## Context
Update API client to use new `/history/*` endpoints instead of deleted `/radio/*` endpoints. Remove station-related parameters.

## Files to Modify/Create
- web/frontend/src/api/radio.ts → **RENAME to history.ts**
- Delete all station-related functions and types

## Implementation Details

### Update `getHistory()`:
```typescript
export async function getHistory(params: {
  limit?: number;
  offset?: number;
  startDate?: string;
  endDate?: string;
}): Promise<HistoryEntry[]> {
  const queryParams = new URLSearchParams();
  if (params.limit) queryParams.set('limit', String(params.limit));
  if (params.offset) queryParams.set('offset', String(params.offset));
  if (params.startDate) queryParams.set('start_date', params.startDate);
  if (params.endDate) queryParams.set('end_date', params.endDate);

  const url = `${API_BASE}/history?${queryParams}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error('Failed to fetch history');
  return response.json();
}
```

### Update `getStationStats()` → rename to `getStats()`:
```typescript
export async function getStats(days: number = 30): Promise<Stats> {
  const response = await fetch(`${API_BASE}/history/stats?days=${days}`);
  if (!response.ok) throw new Error('Failed to fetch stats');
  return response.json();
}
```

### Update `getTopTracks()`:
```typescript
export async function getTopTracks(
  limit: number = 10,
  days: number = 30
): Promise<TopTrack[]> {
  const response = await fetch(
    `${API_BASE}/history/top-tracks?limit=${limit}&days=${days}`
  );
  if (!response.ok) throw new Error('Failed to fetch top tracks');
  return response.json();
}
```

### Update TypeScript interfaces:

```typescript
// history.ts - Clean interfaces without station concepts

interface HistoryEntry {
  id: number;
  track_id: number | null;
  track_title: string;
  track_artist: string;
  source_type: string;
  started_at: string;
  ended_at: string | null;
  duration_ms: number;        // Actual listening time (renamed from position_ms)
  end_reason: string | null;  // 'skip' | 'completed' | 'new_play'
}

interface Stats {
  total_plays: number;
  total_minutes: number;  // Actual listening time
  unique_tracks: number;
}

interface TopTrack {
  track_id: number;
  track_title: string;
  track_artist: string;
  play_count: number;
  total_duration_seconds: number;
}
```

### Delete everything station-related:
- `Station` interface
- `NowPlaying` interface
- `ScheduleEntry` interface
- `CreateStationRequest` interface
- `StationStats` interface (replaced by Stats)
- `getStations()`, `getStation()`, `createStation()`, `updateStation()`, `deleteStation()`
- `activateStation()`, `deactivateStation()`
- `getSchedule()`, `createScheduleEntry()`, `updateScheduleEntry()`, `deleteScheduleEntry()`
- `reorderSchedule()`
- `getNowPlaying()`
- `getStationStats()` (replaced by `getStats()`)

## Verification

1. Open browser DevTools → Network tab
2. Navigate to History page
3. Verify requests go to `/api/history/*` endpoints (not `/api/radio/*`)
4. Check response payloads match new interfaces (no station fields)

```bash
# Or test directly:
curl http://localhost:8642/api/history?limit=10
curl http://localhost:8642/api/history/stats?days=30
curl http://localhost:8642/api/history/top-tracks?limit=5
```
