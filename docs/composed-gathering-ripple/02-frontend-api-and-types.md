# Frontend: API Functions and Types

## Files to Modify/Create
- `web/frontend/src/api/playlists.ts` (modify)
- `web/frontend/src/types.ts` (modify)

## Implementation Details

### Types (`web/frontend/src/types/index.ts`)

Narrow the `Playlist.type` field from `string` to union type:

```typescript
export interface Playlist {
  id: number;
  name: string;
  type: 'manual' | 'smart';  // Changed from string
  description?: string;
  track_count: number;
  library: string;
}
```

### API Functions (`web/frontend/src/api/playlists.ts`)

Add smart playlist filter API functions. **Reuse existing `Filter` type from `api/builder.ts`** (no new type needed):

```typescript
import type { Filter } from './builder';

export const getSmartFilters = async (playlistId: number): Promise<Filter[]> => {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}/filters`);
  if (!response.ok) throw new Error('Failed to fetch filters');
  const data = await response.json();
  return data.filters;
};

export const updateSmartFilters = async (
  playlistId: number,
  filters: Filter[]
): Promise<Filter[]> => {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}/filters`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filters }),
  });
  if (!response.ok) throw new Error('Failed to update filters');
  const data = await response.json();
  return data.filters;
};
```

## Acceptance Criteria
- [ ] `Playlist.type` narrowed from `string` to `'manual' | 'smart'`
- [ ] Reuse existing `Filter` type from `api/builder.ts` (no `SmartFilter` duplication)
- [ ] `getSmartFilters()` function fetches filters from backend
- [ ] `updateSmartFilters()` function sends filter updates to backend
- [ ] Error handling for failed API calls

## Dependencies
- Task 01: Backend endpoints must exist for API to call
