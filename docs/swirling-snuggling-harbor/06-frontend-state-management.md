# Frontend State Management - React Query Hook

## Files to Create
- `web/frontend/src/hooks/useBuilderSession.ts` (new)

## Implementation Details

Create React Query hook for managing builder session state with optimistic updates and caching.

### Hook Implementation

```typescript
// web/frontend/src/hooks/useBuilderSession.ts

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { builderApi, SessionResponse, TrackActionResponse } from '../api/builder';

export function useBuilderSession(playlistId: number | null) {
  const queryClient = useQueryClient();

  // Fetch active session (no polling - rely on optimistic updates)
  const { data: session, isLoading, error } = useQuery({
    queryKey: ['builder-session', playlistId],
    queryFn: () => playlistId ? builderApi.getSession(playlistId) : null,
    enabled: !!playlistId
  });

  // Start session mutation
  const startSession = useMutation({
    mutationFn: (playlistId: number) => builderApi.startSession(playlistId),
    onSuccess: (data) => {
      queryClient.setQueryData(['builder-session', data.playlist_id], data);
    },
    onError: (error: Error) => {
      console.error('Failed to start session:', error);
    }
  });

  // Add track mutation
  const addTrack = useMutation({
    mutationFn: (trackId: number) => {
      if (!playlistId) throw new Error('No playlist selected');
      return builderApi.addTrack(playlistId, trackId);
    },
    onSuccess: () => {
      // Invalidate related queries (component will call getNextCandidate)
      queryClient.invalidateQueries({ queryKey: ['playlists'] });
      queryClient.invalidateQueries({ queryKey: ['builder-candidates', playlistId] });
    },
    onError: (error: Error) => {
      console.error('Failed to add track:', error);
    }
  });

  // Skip track mutation
  const skipTrack = useMutation({
    mutationFn: (trackId: number) => {
      if (!playlistId) throw new Error('No playlist selected');
      return builderApi.skipTrack(playlistId, trackId);
    },
    onSuccess: () => {
      // Invalidate related queries (component will call getNextCandidate)
      queryClient.invalidateQueries({ queryKey: ['builder-skipped', playlistId] });
      queryClient.invalidateQueries({ queryKey: ['builder-candidates', playlistId] });
    },
    onError: (error: Error) => {
      console.error('Failed to skip track:', error);
    }
  });

  // End session mutation
  const endSession = useMutation({
    mutationFn: () => {
      if (!playlistId) throw new Error('No playlist selected');
      return builderApi.endSession(playlistId);
    },
    onSuccess: () => {
      queryClient.removeQueries({ queryKey: ['builder-session', playlistId] });
    }
  });

  // Fetch filters
  const { data: filters } = useQuery({
    queryKey: ['builder-filters', playlistId],
    queryFn: () => playlistId ? builderApi.getFilters(playlistId) : [],
    enabled: !!playlistId
  });

  // Update filters mutation
  const updateFilters = useMutation({
    mutationFn: (filters: any[]) => {
      if (!playlistId) throw new Error('No playlist selected');
      return builderApi.updateFilters(playlistId, filters);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['builder-filters', playlistId] });
      queryClient.invalidateQueries({ queryKey: ['builder-session', playlistId] });
      queryClient.invalidateQueries({ queryKey: ['builder-candidates', playlistId] });
    }
  });

  return {
    // Session state
    session,
    isLoading,
    error,
    currentTrack: session?.current_track,
    stats: session ? {
      candidatesRemaining: session.candidates_remaining,
      startedAt: session.started_at,
      updatedAt: session.updated_at
    } : null,

    // Session mutations
    startSession,
    endSession,

    // Track mutations
    addTrack,
    skipTrack,

    // Filter state
    filters,
    updateFilters,

    // Loading states
    isAddingTrack: addTrack.isPending,
    isSkippingTrack: skipTrack.isPending
  };
}
```

### Usage Example

```typescript
function PlaylistBuilderPage() {
  const [playlistId, setPlaylistId] = useState<number | null>(null);
  const {
    session,
    currentTrack,
    stats,
    addTrack,
    skipTrack,
    isAddingTrack,
    isSkippingTrack
  } = useBuilderSession(playlistId);

  const handleAdd = () => {
    if (currentTrack) {
      addTrack.mutate(currentTrack.id);
    }
  };

  const handleSkip = () => {
    if (currentTrack) {
      skipTrack.mutate(currentTrack.id);
    }
  };

  // ...
}
```

## Acceptance Criteria

1. Hook properly manages session lifecycle
2. Optimistic updates for add/skip operations
3. Automatic refetching every 5 seconds
4. Proper cache invalidation on mutations
5. Error handling with rollback on failures
6. Loading states exposed for UI feedback
7. TypeScript types properly defined
8. Related queries invalidated (playlists, candidates, skipped)

## Dependencies
- Task 05: Frontend API client

## Testing

```typescript
// Manual testing
import { useBuilderSession } from './hooks/useBuilderSession';

function TestComponent() {
  const { session, addTrack, skipTrack } = useBuilderSession(1);

  return (
    <div>
      <p>Current: {session?.current_track?.title}</p>
      <button onClick={() => addTrack.mutate(session.current_track.id)}>
        Add
      </button>
      <button onClick={() => skipTrack.mutate(session.current_track.id)}>
        Skip
      </button>
    </div>
  );
}
```

Verify:
- Session loads on mount
- Add/skip operations update UI immediately (optimistic)
- Network error reverts optimistic update
- Related queries refresh after mutations
