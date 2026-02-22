---
task: 07-organizer-page
status: pending
depends: [05-organizer-hook, 06-organizer-routes]
files:
  - path: web/frontend/src/pages/PlaylistOrganizer.tsx
    action: create
  - path: web/frontend/src/components/organizer/CurrentTrackBanner.tsx
    action: create
  - path: web/frontend/src/components/organizer/UnassignedTrackTable.tsx
    action: create
---

# Main Playlist Organizer Page

## Context
Create the main page component with current track banner, unassigned tracks table, and keyboard handling. This task creates the page shell; bucket components are in the next task.

## Files to Modify/Create
- web/frontend/src/pages/PlaylistOrganizer.tsx (new)
- web/frontend/src/components/organizer/CurrentTrackBanner.tsx (new)
- web/frontend/src/components/organizer/UnassignedTrackTable.tsx (new)

## Implementation Details

### 1. PlaylistOrganizer.tsx

```typescript
import { useEffect, useCallback } from 'react';
import { usePlayerStore } from '../stores/playerStore';
import { usePlaylistOrganizer } from '../hooks/usePlaylistOrganizer';
import { useQuery } from '@tanstack/react-query';
import { getPlaylistTracks } from '../api/playlists';
import CurrentTrackBanner from '../components/organizer/CurrentTrackBanner';
import UnassignedTrackTable from '../components/organizer/UnassignedTrackTable';
import BucketList from '../components/organizer/BucketList';
import { Button } from '../components/ui/button';

interface Props {
  playlistId: number;
  playlistName: string;
  playlistType: 'manual' | 'smart';
}

export default function PlaylistOrganizer({ playlistId, playlistName, playlistType }: Props) {
  const { currentTrack, play, next } = usePlayerStore();

  const {
    session,
    isLoading,
    buckets,
    unassignedTrackIds,
    assignTrack,
    createBucket,
    updateBucket,
    deleteBucket,
    moveBucket,
    shuffleBucket,
    reorderTracks,
    applyOrder,
    getBucketByIndex,
  } = usePlaylistOrganizer({ playlistId });

  // Load full track data for unassigned tracks
  const { data: allTracks } = useQuery({
    queryKey: ['playlist', playlistId, 'tracks'],
    queryFn: () => getPlaylistTracks(playlistId),
  });

  // Use Set for O(1) lookup instead of O(n) includes()
  const unassignedSet = new Set(unassignedTrackIds);
  const unassignedTracks = allTracks?.filter((t) => unassignedSet.has(t.id)) ?? [];

  // Keyboard handler for Shift+1-0
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!e.shiftKey) return;
      if (!currentTrack) return;

      // Check if typing in an input
      const target = e.target as HTMLElement;
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return;

      const num = parseInt(e.key);
      if (isNaN(num)) return;

      e.preventDefault();

      // Shift+1 = bucket index 0, Shift+0 = bucket index 9
      const bucketIndex = num === 0 ? 9 : num - 1;
      const bucket = getBucketByIndex(bucketIndex);

      if (bucket) {
        handleAssignCurrentTrack(bucket.id);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [buckets, currentTrack, getBucketByIndex, handleAssignCurrentTrack]);

  const handleAssignCurrentTrack = useCallback(
    async (bucketId: string) => {
      if (!currentTrack) return;

      await assignTrack(bucketId, currentTrack.id);

      // Auto-advance to next unassigned track
      const remainingUnassigned = unassignedTrackIds.filter((id) => id !== currentTrack.id);
      if (remainingUnassigned.length > 0) {
        const nextTrack = allTracks?.find((t) => t.id === remainingUnassigned[0]);
        if (nextTrack) {
          await play(nextTrack, { type: 'playlist', playlist_id: playlistId });
        }
      }
    },
    [currentTrack, assignTrack, unassignedTrackIds, allTracks, play, playlistId]
  );

  const handlePlayTrack = useCallback(
    (trackId: number) => {
      const track = allTracks?.find((t) => t.id === trackId);
      if (track) {
        play(track, { type: 'playlist', playlist_id: playlistId });
      }
    },
    [allTracks, play, playlistId]
  );

  const handleApplyOrder = useCallback(async () => {
    await applyOrder();
    // Could show toast or navigate away
  }, [applyOrder]);

  if (isLoading) {
    return <div className="p-4">Loading organizer...</div>;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <h1 className="text-xl font-bold">{playlistName} - Organizer</h1>
        <Button onClick={handleApplyOrder} disabled={buckets.length === 0}>
          Apply Order
        </Button>
      </div>

      {/* Current Track Banner */}
      <CurrentTrackBanner
        currentTrack={currentTrack}
        buckets={buckets}
        onAssign={handleAssignCurrentTrack}
      />

      {/* Main content - scrollable */}
      <div className="flex-1 overflow-auto p-4 space-y-6">
        {/* Unassigned tracks */}
        <section>
          <h2 className="text-lg font-semibold mb-2">
            Unassigned Tracks ({unassignedTracks.length})
          </h2>
          <UnassignedTrackTable
            tracks={unassignedTracks}
            currentTrackId={currentTrack?.id}
            onPlayTrack={handlePlayTrack}
          />
        </section>

        {/* Buckets */}
        <section>
          <BucketList
            buckets={buckets}
            allTracks={allTracks ?? []}
            sessionId={session?.id ?? ''}
            onCreateBucket={createBucket}
            onMoveBucket={moveBucket}
            onShuffleBucket={shuffleBucket}
            onDeleteBucket={deleteBucket}
            onUpdateBucket={updateBucket}
            onReorderTracks={reorderTracks}
          />
        </section>
      </div>
    </div>
  );
}
```

### 2. CurrentTrackBanner.tsx

```typescript
import { Track } from '../../stores/playerStore';
import { Bucket } from '../../api/buckets';
import { Progress } from '../ui/progress';
import { usePlayerStore, getCurrentPosition } from '../../stores/playerStore';

interface Props {
  currentTrack: Track | null;
  buckets: Bucket[];
  onAssign: (bucketId: string) => void;
}

export default function CurrentTrackBanner({ currentTrack, buckets, onAssign }: Props) {
  const playerState = usePlayerStore();
  const position = getCurrentPosition(playerState);
  const duration = currentTrack?.duration ?? 0;
  const progress = duration > 0 ? (position / (duration * 1000)) * 100 : 0;

  if (!currentTrack) {
    return (
      <div className="p-4 bg-muted/50 border-b">
        <p className="text-muted-foreground">No track playing. Select a track to start.</p>
      </div>
    );
  }

  return (
    <div className="p-4 bg-muted/50 border-b">
      <div className="flex items-center justify-between mb-2">
        <div>
          <p className="font-medium">{currentTrack.title}</p>
          <p className="text-sm text-muted-foreground">{currentTrack.artist}</p>
        </div>
        <div className="text-sm text-muted-foreground">
          Shift+1-{Math.min(buckets.length, 9)} to assign
          {buckets.length >= 10 && ', Shift+0 for bucket 10'}
        </div>
      </div>
      <Progress value={progress} className="h-1" />
    </div>
  );
}
```

### 3. UnassignedTrackTable.tsx

Simplified TanStack Table, similar to TrackQueueTable:

```typescript
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from '@tanstack/react-table';
import { cn } from '../../lib/utils';

interface Track {
  id: number;
  title: string;
  artist?: string;
  bpm?: number;
  key_signature?: string;
  rating?: number;
}

interface Props {
  tracks: Track[];
  currentTrackId?: number;
  onPlayTrack: (trackId: number) => void;
}

const columnHelper = createColumnHelper<Track>();

const columns = [
  columnHelper.accessor('title', {
    header: 'Title',
    cell: (info) => <span className="font-medium">{info.getValue()}</span>,
  }),
  columnHelper.accessor('artist', {
    header: 'Artist',
  }),
  columnHelper.accessor('bpm', {
    header: 'BPM',
    size: 60,
  }),
  columnHelper.accessor('key_signature', {
    header: 'Key',
    size: 50,
  }),
  columnHelper.accessor('rating', {
    header: 'Rating',
    size: 80,
    cell: (info) => {
      const rating = info.getValue() ?? 0;
      return '★'.repeat(rating) + '☆'.repeat(5 - rating);
    },
  }),
];

export default function UnassignedTrackTable({ tracks, currentTrackId, onPlayTrack }: Props) {
  const table = useReactTable({
    data: tracks,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="border rounded-md overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-muted">
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  className="px-3 py-2 text-left font-medium"
                  style={{ width: header.getSize() }}
                >
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              className={cn(
                'border-t cursor-pointer hover:bg-muted/50',
                row.original.id === currentTrackId && 'bg-primary/10'
              )}
              onClick={() => onPlayTrack(row.original.id)}
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-3 py-2">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {tracks.length === 0 && (
        <div className="p-4 text-center text-muted-foreground">
          All tracks have been assigned to buckets.
        </div>
      )}
    </div>
  );
}
```

## Verification
```bash
# Start dev server
uv run music-minion --web

# Navigate to /playlist-organizer/{id}
# Should see:
# - Header with playlist name and Apply Order button
# - Current track banner (or "no track" message)
# - Unassigned tracks table
# - Empty buckets section (BucketList not yet implemented)

# Click a row in the table
# Should start playing that track
```
