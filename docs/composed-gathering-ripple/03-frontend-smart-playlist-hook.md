# Frontend: Smart Playlist Editor Hook

## Files to Modify/Create
- `web/frontend/src/hooks/useSmartPlaylistEditor.ts` (new)

## Implementation Details

Create a new hook that manages smart playlist state, similar to `useBuilderSession` but for smart playlists:

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSmartFilters, updateSmartFilters, SmartFilter } from '../api/playlists';

interface SmartPlaylistTrack {
  id: number;
  title: string;
  artist: string;
  album?: string;
  genre?: string;
  year?: number;
  bpm?: number;
  key_signature?: string;
  elo_rating?: number;
}

export function useSmartPlaylistEditor(playlistId: number) {
  const queryClient = useQueryClient();

  // Fetch filters for the smart playlist
  const filtersQuery = useQuery({
    queryKey: ['smart-playlist-filters', playlistId],
    queryFn: () => getSmartFilters(playlistId),
    enabled: !!playlistId,
  });

  // Fetch tracks matching the filters (uses existing endpoint)
  const tracksQuery = useQuery({
    queryKey: ['playlist-tracks', playlistId],
    queryFn: async () => {
      const response = await fetch(`/api/playlists/${playlistId}/tracks`);
      if (!response.ok) throw new Error('Failed to fetch tracks');
      const data = await response.json();
      return data.tracks as SmartPlaylistTrack[];
    },
    enabled: !!playlistId,
  });

  // Mutation to update filters
  const updateFiltersMutation = useMutation({
    mutationFn: (filters: SmartFilter[]) => updateSmartFilters(playlistId, filters),
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
  };
}
```

## Key Differences from `useBuilderSession`
- No session management (smart playlists don't need sessions)
- Filters are permanent (stored in `playlist_filters` table)
- Tracks are read-only (no add/skip mutations)
- Track list refreshes when filters change

## Acceptance Criteria
- [ ] Hook fetches filters via `getSmartFilters()`
- [ ] Hook fetches tracks via existing `/playlists/{id}/tracks` endpoint
- [ ] `updateFilters` mutation invalidates both filters and tracks queries
- [ ] Loading states properly reflect async operations
- [ ] Filter updates trigger track list refresh

## Dependencies
- Task 02: API functions must exist
