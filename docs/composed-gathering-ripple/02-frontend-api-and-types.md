# Frontend: API Functions and Types

## Files to Modify/Create
- `web/frontend/src/api/playlists.ts` (modify)
- `web/frontend/src/types.ts` (modify)

## Implementation Details

### Types (`web/frontend/src/types.ts`)

Ensure `Playlist` type includes the `type` field:

```typescript
export interface Playlist {
  id: number;
  name: string;
  type: 'manual' | 'smart';  // Ensure this exists
  description?: string;
  track_count: number;
  library: string;
  // ... other fields
}
```

### API Functions (`web/frontend/src/api/playlists.ts`)

Add smart playlist filter API functions:

```typescript
export interface SmartFilter {
  id?: number;  // Optional for new filters
  field: string;
  operator: string;
  value: string;
  conjunction: 'AND' | 'OR';
}

export const getSmartFilters = async (playlistId: number): Promise<SmartFilter[]> => {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}/filters`);
  if (!response.ok) throw new Error('Failed to fetch filters');
  const data = await response.json();
  return data.filters;
};

export const updateSmartFilters = async (
  playlistId: number,
  filters: SmartFilter[]
): Promise<SmartFilter[]> => {
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
- [ ] `Playlist` type includes `type: 'manual' | 'smart'`
- [ ] `SmartFilter` interface defined with all required fields
- [ ] `getSmartFilters()` function fetches filters from backend
- [ ] `updateSmartFilters()` function sends filter updates to backend
- [ ] Error handling for failed API calls

## Dependencies
- Task 01: Backend endpoints must exist for API to call
