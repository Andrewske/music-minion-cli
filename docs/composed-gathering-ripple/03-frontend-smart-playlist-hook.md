# Frontend: Smart Playlist Editor Hook

## Files to Modify/Create
- `web/frontend/src/hooks/useSmartPlaylistEditor.ts` (new)

## Implementation Details

Create a new hook that manages smart playlist state, similar to `useBuilderSession` but for smart playlists:

```typescript
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { SortingState } from '@tanstack/react-table';
import { getSmartFilters, updateSmartFilters } from '../api/playlists';
import type { Filter, Track } from '../api/builder';

export function useSmartPlaylistEditor(playlistId: number) {
  const queryClient = useQueryClient();

  // Sorting state - mirrors manual builder pattern
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'artist', desc: false }
  ]);
  const sortField = sorting[0]?.id ?? 'artist';
  const sortDirection = sorting[0]?.desc ? 'desc' : 'asc';

  // Fetch filters for the smart playlist
  const filtersQuery = useQuery({
    queryKey: ['smart-playlist-filters', playlistId],
    queryFn: () => getSmartFilters(playlistId),
    enabled: !!playlistId,
  });

  // Fetch tracks matching the filters with server-side sorting
  const tracksQuery = useQuery({
    queryKey: ['playlist-tracks', playlistId, sortField, sortDirection],
    queryFn: async () => {
      const response = await fetch(
        `/api/playlists/${playlistId}/tracks?sort_field=${sortField}&sort_direction=${sortDirection}`
      );
      if (!response.ok) throw new Error('Failed to fetch tracks');
      const data = await response.json();
      return data.tracks as Track[];
    },
    enabled: !!playlistId,
  });

  // Mutation to update filters
  const updateFiltersMutation = useMutation({
    mutationFn: (filters: Filter[]) => updateSmartFilters(playlistId, filters),
    onSuccess: () => {
      // Invalidate both filters and tracks (tracks depend on filters)
      queryClient.invalidateQueries({ queryKey: ['smart-playlist-filters', playlistId] });
      queryClient.invalidateQueries({ queryKey: ['playlist-tracks', playlistId] });
    },
  });

  return {
    filters: filtersQuery.data ?? [],
    tracks: tracksQuery.data ?? [],
    isLoading: filtersQuery.isLoading || tracksQuery.isLoading,
    isUpdatingFilters: updateFiltersMutation.isPending,
    updateFilters: updateFiltersMutation,
    refetchTracks: tracksQuery.refetch,
    sorting,
    setSorting,
  };
}
```

## Key Differences from `useBuilderSession`
- No session management (smart playlists don't need sessions)
- Filters are permanent (stored in `playlist_filters` table)
- Tracks are read-only (no add/skip mutations)
- Track list refreshes when filters change
- Server-side sorting via query params (same pattern as manual builder)

## Pagination Note
Pagination is deferred for MVP. Rationale:
- Smart playlists are typically curated subsets (genre filters, year ranges), not full-library queries
- TrackQueueTable uses virtualization for render performance
- Revisit if users report slow load times with 1000+ track smart playlists

## Acceptance Criteria
- [ ] Hook fetches filters via `getSmartFilters()`
- [ ] Hook fetches tracks via `/playlists/{id}/tracks` with sort params
- [ ] `updateFilters` mutation invalidates both filters and tracks queries
- [ ] Sorting state exposed for TrackQueueTable integration
- [ ] Loading states properly reflect async operations
- [ ] Filter updates trigger track list refresh

## Dependencies
- Task 02: API functions must exist
