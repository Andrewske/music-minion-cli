# Create TrackQueueTable Component

## Files to Modify/Create
- web/frontend/src/components/builder/TrackQueueTable.tsx (new)

## Implementation Details

Create a new virtualized table component using TanStack Table and TanStack Virtual.

### Component Props

```typescript
interface TrackQueueTableProps {
  tracks: Track[];
  queueIndex: number;           // Current position in queue
  nowPlayingId: number | null;  // Currently playing track ID
  onTrackClick: (track: Track) => void;
  sorting: SortingState;
  onSortingChange: (sorting: SortingState) => void;
  // Infinite scroll
  onLoadMore: () => void;
  hasMore: boolean;
  isLoadingMore: boolean;
}
```

### Column Definitions

| Column | Accessor | Type | Sortable | Width |
|--------|----------|------|----------|-------|
| Title | `title` | string | yes | 180px |
| Artist | `artist` | string | yes | 150px |
| BPM | `bpm` | number | yes | 60px |
| Genre | `genre` | string | yes | 100px |
| Key | `key_signature` | string | yes | 60px |
| Year | `year` | number | yes | 60px |
| Rating | `elo_rating` | number | yes | 70px |

### TanStack Table Setup

Note: Server handles actual sorting. TanStack Table captures sort intent via column clicks and displays pre-sorted data.

```typescript
const table = useReactTable({
  data: tracks,  // Already sorted by server
  columns,
  state: { sorting },
  onSortingChange,  // Bubbles up to parent, triggers server refetch
  getCoreRowModel: getCoreRowModel(),
  manualSorting: true,  // Tell TanStack we handle sorting externally
  enableSortingRemoval: false,  // Cycle asc → desc → asc, never empty
});
```

### Virtual Scrolling + Infinite Load Configuration

```typescript
import { useVirtualizer } from '@tanstack/react-virtual';

const parentRef = useRef<HTMLDivElement>(null);

const virtualizer = useVirtualizer({
  count: tracks.length,
  getScrollElement: () => parentRef.current,
  estimateSize: () => 40,  // Row height in pixels
  overscan: 5,
});

// Trigger load more when scrolling near bottom
useEffect(() => {
  const lastItem = virtualizer.getVirtualItems().at(-1);
  if (!lastItem) return;

  // Load more when within 5 rows of the end
  if (lastItem.index >= tracks.length - 5 && hasMore && !isLoadingMore) {
    onLoadMore();
  }
}, [virtualizer.getVirtualItems(), hasMore, isLoadingMore, tracks.length, onLoadMore]);
```

- Container: `max-h-[50vh]` or `h-[400px]` with `overflow-auto`
- Overscan: 5 rows for smooth scrolling
- Load trigger: 5 rows before end

### Styling
- Table container: `bg-slate-800 rounded-lg overflow-hidden`
- Headers: `bg-slate-700 cursor-pointer hover:bg-slate-600`
- Sort indicators: Arrow icons (up/down) on sorted column
- Row at queueIndex: `bg-blue-900/30 border-l-2 border-blue-500`
- nowPlaying row: `bg-green-900/30 border-l-2 border-green-500`
- Row hover: `hover:bg-slate-700`

## Acceptance Criteria
- [ ] Component renders table with all 7 columns (Title, Artist, BPM, Genre, Key, Year, Rating)
- [ ] Clicking column headers triggers `onSortingChange`
- [ ] Sort direction indicator shows on sorted column
- [ ] Clicking a row calls `onTrackClick` with the track (no-op if already playing)
- [ ] Queue position row has blue highlight
- [ ] Now playing row has green highlight
- [ ] Virtual scrolling works (only visible rows rendered)
- [ ] Scrolling near bottom triggers `onLoadMore` when `hasMore` is true
- [ ] Loading indicator shows when `isLoadingMore` is true
- [ ] No TypeScript errors

## Dependencies
- Task 01: TanStack packages must be installed
