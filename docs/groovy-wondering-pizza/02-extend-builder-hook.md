---
task: 02-extend-builder-hook
status: pending
depends:
  - 00-backend-pagination
files:
  - path: web/frontend/src/hooks/usePlaylistBuilder.ts
    action: create
  - path: web/frontend/src/hooks/useBuilderSession.ts
    action: delete
---

# Create Unified usePlaylistBuilder Hook

## Context
Replace separate hooks (`useBuilderSession`, `useSmartPlaylistEditor`) with a single unified hook that handles both playlist types. Sessions are removed - skips are permanent for both types.

## Files to Modify/Create
- `web/frontend/src/hooks/usePlaylistBuilder.ts` (new)
- `web/frontend/src/hooks/useBuilderSession.ts` (delete after migration)

## Implementation Details

### Hook Signature
```typescript
function usePlaylistBuilder(playlistId: number, playlistType: 'manual' | 'smart')
```

No session parameter - sessions are removed entirely.

### Hook Owns Sorting State
```typescript
const [sorting, setSorting] = useState<SortingState>([
  { id: 'artist', desc: false }
]);
const sortField = sorting[0]?.id ?? 'artist';
const sortDirection = sorting[0]?.desc ? 'desc' : 'asc';
```

### Unified Infinite Query
Both types use `useInfiniteQuery` with pagination:

```typescript
const {
  data,
  fetchNextPage,
  hasNextPage,
  isFetchingNextPage,
} = useInfiniteQuery({
  queryKey: ['builder-tracks', playlistId, playlistType, sortField, sortDirection],
  queryFn: ({ pageParam = 0 }) =>
    playlistType === 'manual'
      ? builderApi.getCandidates(playlistId, PAGE_SIZE, pageParam, sortField, sortDirection)
      : getSmartPlaylistTracks(playlistId, PAGE_SIZE, pageParam, sortField, sortDirection),
  initialPageParam: 0,
  getNextPageParam: (lastPage, allPages) =>
    lastPage.hasMore ? allPages.length * PAGE_SIZE : undefined,
  enabled: !!playlistId,
});

const tracks = data?.pages.flatMap(p => p.tracks ?? p.candidates) ?? [];
```

### Skip Mutations (unified, permanent)
Both types use the same skip pattern - skips are permanent (no sessions):

```typescript
const skipTrack = useMutation({
  mutationFn: (trackId: number) =>
    playlistType === 'manual'
      ? builderApi.skipTrack(playlistId, trackId)
      : skipSmartPlaylistTrack(playlistId, trackId),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['builder-tracks', playlistId] });
    queryClient.invalidateQueries({ queryKey: ['builder-skipped', playlistId] });
  },
});
```

### Return Type
```typescript
interface UsePlaylistBuilderReturn {
  // Tracks
  tracks: Track[];
  fetchNextPage: () => void;
  hasNextPage: boolean;
  isFetchingNextPage: boolean;

  // Sorting (hook owns state)
  sorting: SortingState;
  setSorting: (sorting: SortingState) => void;

  // Mutations
  addTrack: UseMutationResult;  // Only used for manual
  skipTrack: UseMutationResult;
  unskipTrack: UseMutationResult;

  // Skipped tracks
  skippedTracks: Track[];

  // Filters (smart playlists)
  filters: Filter[];
  updateFilters: UseMutationResult;

  // Loading states
  isLoading: boolean;
  isAddingTrack: boolean;
  isSkippingTrack: boolean;
}
```

### Query Keys
- Tracks: `['builder-tracks', playlistId, playlistType, sortField, sortDirection]`
- Skipped: `['builder-skipped', playlistId, playlistType]`
- Filters: `['builder-filters', playlistId]` (smart only)

## Verification
1. Hook compiles without TypeScript errors
2. Both playlist types fetch tracks via infinite query
3. Sorting state lives in hook, returned for table binding
4. Skip mutations work for both types (permanent, no sessions)
5. No session-related code remains
