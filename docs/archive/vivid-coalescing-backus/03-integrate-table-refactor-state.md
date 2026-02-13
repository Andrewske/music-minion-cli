# Integrate Table and Refactor State Model

## Files to Modify/Create
- web/backend/routers/builder.py (modify)
- src/music_minion/domain/playlists/builder.py (modify)
- web/frontend/src/api/builder.ts (modify)
- web/frontend/src/pages/PlaylistBuilder.tsx (modify)
- web/frontend/src/hooks/useBuilderSession.ts (modify)
- web/frontend/src/components/builder/SortControl.tsx (delete)

## Implementation Details

### Backend: Server-Side Sorting

**src/music_minion/domain/playlists/builder.py** - Modify `get_candidate_tracks()`:

```python
def get_candidate_tracks(
    playlist_id: int,
    sort_field: str = 'artist',
    sort_direction: str = 'asc',
    limit: int = 100,
    offset: int = 0
) -> tuple[list[dict], int]:
    """Get paginated candidate tracks with server-side sorting.

    Args:
        playlist_id: Playlist ID
        sort_field: Column to sort by (artist, title, year, bpm, genre, key_signature, elo_rating)
        sort_direction: 'asc' or 'desc'
        limit: Tracks per page (default 100)
        offset: Number of tracks to skip

    Returns:
        Tuple of (tracks list, total count)
    """
    # Validate sort_field against allowlist to prevent SQL injection
    ALLOWED_SORT_FIELDS = {'artist', 'title', 'year', 'bpm', 'genre', 'key_signature', 'elo_rating'}
    if sort_field not in ALLOWED_SORT_FIELDS:
        sort_field = 'artist'

    # Map elo_rating to the computed column
    order_column = 'COALESCE(er.rating, 1500.0)' if sort_field == 'elo_rating' else f't.{sort_field}'
    order_dir = 'DESC' if sort_direction == 'desc' else 'ASC'

    # First get total count (without LIMIT/OFFSET)
    count_query = """...existing WHERE clause..."""
    # Execute count_query to get total

    # Then get paginated results
    query = f"""
        ...existing query...
        ORDER BY {order_column} {order_dir} NULLS LAST, t.id ASC
        LIMIT ? OFFSET ?
    """
    # Return (tracks, total_count)
```

**web/backend/routers/builder.py** - Add query params to `/candidates/{playlist_id}`:

```python
@router.get("/candidates/{playlist_id}", response_model=CandidatesResponse)
async def get_candidates(
    playlist_id: int,
    limit: int = 100,
    offset: int = 0,
    sort_field: str = 'artist',
    sort_direction: str = 'asc'
):
    _validate_manual_playlist(playlist_id)

    candidates, total = builder.get_candidate_tracks(
        playlist_id,
        sort_field=sort_field,
        sort_direction=sort_direction,
        limit=limit,
        offset=offset
    )

    return CandidatesResponse(
        candidates=candidates,
        total=total,
        limit=limit,
        offset=offset,
    )
```

**web/frontend/src/api/builder.ts** - Update `getCandidates()`:

```typescript
getCandidates: async (
  playlistId: number,
  limit: number = 100,
  offset: number = 0,
  sortField: string = 'artist',
  sortDirection: string = 'asc'
): Promise<{ candidates: Track[]; total: number; hasMore: boolean }> => {
  const res = await fetch(
    `${API_BASE}/builder/candidates/${playlistId}?limit=${limit}&offset=${offset}&sort_field=${sortField}&sort_direction=${sortDirection}`
  );
  const data = await res.json();
  return {
    ...data,
    hasMore: offset + data.candidates.length < data.total
  };
}
```

### State Model Changes

Introduce two distinct track concepts:

1. **queueTrackId** - Track ID at current queue position (survives sort changes)
2. **nowPlayingTrack** - Currently playing track (may differ from queue when user clicks a row)

Why track by ID instead of index: When sort order changes, an array index points to a different track. Tracking by ID ensures the queue position is semantically stable.

### PlaylistBuilder.tsx Changes

**Add state:**
```typescript
// Track queue by ID, not index - survives sort changes
const [queueTrackId, setQueueTrackId] = useState<number | null>(null);
const [nowPlayingTrack, setNowPlayingTrack] = useState<Track | null>(null);

// Sorting state - controls server-side sort via API params
const [sorting, setSorting] = useState<SortingState>([
  { id: 'artist', desc: false }
]);

// Derive sort params from TanStack state
const sortField = sorting[0]?.id ?? 'artist';
const sortDirection = sorting[0]?.desc ? 'desc' : 'asc';
```

**Use useInfiniteQuery for paginated loading:**
```typescript
import { useInfiniteQuery } from '@tanstack/react-query';

const PAGE_SIZE = 100;

const {
  data: candidatesData,
  fetchNextPage,
  hasNextPage,
  isFetchingNextPage,
} = useInfiniteQuery({
  queryKey: ['builder-candidates', playlistId, sortField, sortDirection],
  queryFn: ({ pageParam = 0 }) =>
    builderApi.getCandidates(playlistId, PAGE_SIZE, pageParam, sortField, sortDirection),
  initialPageParam: 0,
  getNextPageParam: (lastPage, allPages) =>
    lastPage.hasMore ? allPages.length * PAGE_SIZE : undefined,
  enabled: !!playlistId && !!session,
});

// Flatten pages into single array for table display
const candidates = candidatesData?.pages.flatMap(p => p.candidates) ?? [];
```

**Derive queue index from ID:**
```typescript
// candidates already defined above from flatMap
const queueIndex = queueTrackId
  ? candidates.findIndex(t => t.id === queueTrackId)
  : 0;

// If queueTrackId not found (filtered out), reset to first track
useEffect(() => {
  if (candidates.length > 0 && (queueTrackId === null || queueIndex === -1)) {
    setQueueTrackId(candidates[0].id);
  }
}, [candidates, queueTrackId, queueIndex]);
```

**Remove:**
- `SortControl` component import and usage
- `sortField`, `sortDirection`, `setSortField`, `setSortDirection` from useBuilderSession
- Client-side sorting in useQuery's `select` function

**Add TrackQueueTable:**
Place below the waveform player and action buttons:

```tsx
<TrackQueueTable
  tracks={candidates}
  queueIndex={queueIndex >= 0 ? queueIndex : 0}
  nowPlayingId={nowPlayingTrack?.id ?? null}
  onTrackClick={(track) => {
    // No-op if clicking already-playing track
    if (track.id === nowPlayingTrack?.id) return;
    setNowPlayingTrack(track);
  }}
  sorting={sorting}
  onSortingChange={setSorting}
  // Infinite scroll props
  onLoadMore={() => fetchNextPage()}
  hasMore={hasNextPage ?? false}
  isLoadingMore={isFetchingNextPage}
/>
```

**Update track derivation:**
- Current track for display = `nowPlayingTrack ?? candidates[queueIndex]`
- On Add/Skip: find next track ID, set `queueTrackId` to it, clear `nowPlayingTrack`

```typescript
const handleAdd = async () => {
  const trackToAdd = nowPlayingTrack ?? candidates[queueIndex];
  if (!trackToAdd) return;

  await addTrack.mutateAsync(trackToAdd.id);

  // Advance queue to next track by ID
  const nextIndex = queueIndex + 1;
  if (nextIndex < candidates.length) {
    setQueueTrackId(candidates[nextIndex].id);
  }
  setNowPlayingTrack(null); // Clear preview state
};
```

### useBuilderSession.ts Changes

Remove:
- `sortField` state
- `sortDirection` state
- `setSortField` function
- `setSortDirection` function
- Return values for these

### Layout Structure

```
+-------------------------------------+
|  Track Display (title, artist, tags)|
+-------------------------------------+
|  Waveform Player                    |
+-------------------------------------+
|  [Loop checkbox]                    |
+-------------------------------------+
|  [Add to Playlist]  [Skip]          |
+-------------------------------------+
|  Track Queue Table (scrollable)     |
+-------------------------------------+
```

### Delete SortControl.tsx

The SortControl component is no longer needed - table headers handle sorting.

## Acceptance Criteria

### Backend
- [ ] `/api/builder/candidates/{id}?sort_field=bpm&sort_direction=desc` returns tracks sorted by BPM descending
- [ ] `/api/builder/candidates/{id}?offset=100&limit=100` returns second page of results
- [ ] Response includes `total` count for pagination
- [ ] Invalid sort_field falls back to 'artist' (no 500 error)

### Frontend
- [ ] Table appears below action buttons in PlaylistBuilder
- [ ] Clicking a table row plays that track without advancing queue
- [ ] Add/Skip buttons advance queue to next track (by ID, not index)
- [ ] Sorting via column headers triggers server refetch with new sort params
- [ ] Queue position survives sort changes (same track stays highlighted)
- [ ] Queue position (blue) and now playing (green) are visually distinct
- [ ] Scrolling near bottom loads more tracks (infinite scroll)
- [ ] Sort change resets to first page (clears infinite query cache)
- [ ] SortControl dropdown no longer appears in header
- [ ] No TypeScript errors after removing sort state from hook
- [ ] Existing keyboard shortcuts (space, 0-9) still work

## Dependencies
- Task 01: TanStack packages installed
- Task 02: TrackQueueTable component created
