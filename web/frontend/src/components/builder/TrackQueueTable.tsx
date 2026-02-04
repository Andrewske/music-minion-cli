import { useRef, useEffect } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type SortingState,
  type ColumnDef,
} from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { Track } from '../../api/builder';

interface TrackQueueTableProps {
  tracks: Track[];
  queueIndex: number;
  nowPlayingId: number | null;
  onTrackClick: (track: Track) => void;
  sorting: SortingState;
  onSortingChange: (sorting: SortingState) => void;
  onLoadMore: () => void;
  hasMore: boolean;
  isLoadingMore: boolean;
}

export const TrackQueueTable = ({
  tracks,
  queueIndex,
  nowPlayingId,
  onTrackClick,
  sorting,
  onSortingChange,
  onLoadMore,
  hasMore,
  isLoadingMore,
}: TrackQueueTableProps) => {
  const parentRef = useRef<HTMLDivElement>(null);

  // Column definitions
  const columns: ColumnDef<Track>[] = [
    {
      id: 'title',
      accessorKey: 'title',
      header: 'Title',
      cell: (info) => info.getValue() ?? '-',
      size: 180,
    },
    {
      id: 'artist',
      accessorKey: 'artist',
      header: 'Artist',
      cell: (info) => info.getValue() ?? '-',
      size: 150,
    },
    {
      id: 'bpm',
      accessorKey: 'bpm',
      header: 'BPM',
      cell: (info) => {
        const val = info.getValue() as number | undefined;
        return val ? Math.round(val) : '-';
      },
      size: 60,
    },
    {
      id: 'genre',
      accessorKey: 'genre',
      header: 'Genre',
      cell: (info) => info.getValue() ?? '-',
      size: 100,
    },
    {
      id: 'key_signature',
      accessorKey: 'key_signature',
      header: 'Key',
      cell: (info) => info.getValue() ?? '-',
      size: 60,
    },
    {
      id: 'year',
      accessorKey: 'year',
      header: 'Year',
      cell: (info) => info.getValue() ?? '-',
      size: 60,
    },
    {
      id: 'elo_rating',
      accessorKey: 'elo_rating',
      header: 'Rating',
      cell: (info) => {
        const val = info.getValue() as number | undefined;
        return val ? Math.round(val) : '-';
      },
      size: 70,
    },
  ];

  // TanStack Table setup with manual sorting
  const table = useReactTable({
    data: tracks,
    columns,
    state: { sorting },
    onSortingChange: (updaterOrValue) => {
      const newValue = typeof updaterOrValue === 'function'
        ? updaterOrValue(sorting)
        : updaterOrValue;
      onSortingChange(newValue);
    },
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    enableSortingRemoval: false,
  });

  // Virtual scrolling setup
  const virtualizer = useVirtualizer({
    count: tracks.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 40,
    overscan: 5,
  });

  // Trigger load more when scrolling near bottom
  useEffect(() => {
    const lastItem = virtualizer.getVirtualItems().at(-1);
    if (!lastItem) return;

    if (lastItem.index >= tracks.length - 5 && hasMore && !isLoadingMore) {
      onLoadMore();
    }
  }, [virtualizer.getVirtualItems(), hasMore, isLoadingMore, tracks.length, onLoadMore]);

  // Helper to get row highlight classes
  const getRowClasses = (index: number, trackId: number): string => {
    const isQueue = index === queueIndex;
    const isPlaying = trackId === nowPlayingId;

    let classes = 'cursor-pointer hover:bg-slate-700 ';

    if (isPlaying) {
      classes += 'bg-green-900/30 border-l-2 border-green-500 ';
    } else if (isQueue) {
      classes += 'bg-blue-900/30 border-l-2 border-blue-500 ';
    }

    return classes;
  };

  // Helper to render sort indicator
  const getSortIndicator = (columnId: string): JSX.Element | null => {
    const sortState = sorting.find((s) => s.id === columnId);
    if (!sortState) return null;

    return (
      <span className="ml-1 text-xs">
        {sortState.desc ? '▼' : '▲'}
      </span>
    );
  };

  return (
    <div className="bg-slate-800 rounded-lg overflow-hidden">
      <div
        ref={parentRef}
        className="overflow-auto"
        style={{ maxHeight: '50vh' }}
      >
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-slate-700 z-10">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-3 py-2 text-left cursor-pointer hover:bg-slate-600 select-none"
                    style={{ width: header.column.getSize() }}
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <div className="flex items-center">
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                      {getSortIndicator(header.id)}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody
            style={{
              height: `${virtualizer.getTotalSize()}px`,
              position: 'relative',
            }}
          >
            {virtualizer.getVirtualItems().map((virtualRow) => {
              const row = table.getRowModel().rows[virtualRow.index];
              const track = tracks[virtualRow.index];

              return (
                <tr
                  key={row.id}
                  className={getRowClasses(virtualRow.index, track.id)}
                  onClick={() => onTrackClick(track)}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: `${virtualRow.size}px`,
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className="px-3 py-2 border-b border-slate-700"
                      style={{ width: cell.column.getSize() }}
                    >
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Loading indicator */}
      {isLoadingMore && (
        <div className="text-center py-2 text-slate-400 text-sm">
          Loading more tracks...
        </div>
      )}
    </div>
  );
};
