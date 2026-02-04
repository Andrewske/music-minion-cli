import { useRef, useEffect } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type SortingState,
  type ColumnDef,
  type Column,
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
  // Fixed columns: exact pixel width (flex: 0 0 Xpx)
  // Flexible columns: grow to fill space (flex: X 1 0)
  const columns: ColumnDef<Track>[] = [
    {
      id: 'title',
      accessorKey: 'title',
      header: 'Title',
      cell: (info) => info.getValue() ?? '-',
      size: 3,
      meta: { flexible: true },
    },
    {
      id: 'artist',
      accessorKey: 'artist',
      header: 'Artist',
      cell: (info) => info.getValue() ?? '-',
      size: 2,
      meta: { flexible: true },
    },
    {
      id: 'bpm',
      accessorKey: 'bpm',
      header: 'BPM',
      cell: (info) => {
        const val = info.getValue() as number | undefined;
        return val ? Math.round(val) : '-';
      },
      size: 50,
      meta: { fixed: true },
    },
    {
      id: 'genre',
      accessorKey: 'genre',
      header: 'Genre',
      cell: (info) => info.getValue() ?? '-',
      size: 1,
      meta: { flexible: true },
    },
    {
      id: 'key_signature',
      accessorKey: 'key_signature',
      header: 'Key',
      cell: (info) => info.getValue() ?? '-',
      size: 60,
      meta: { fixed: true },
    },
    {
      id: 'year',
      accessorKey: 'year',
      header: 'Year',
      cell: (info) => info.getValue() ?? '-',
      size: 65,
      meta: { fixed: true },
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
      meta: { fixed: true },
    },
  ];

  // Helper to get flex style for fixed vs flexible columns
  const getColumnFlex = (column: Column<Track>): React.CSSProperties => {
    const meta = column.columnDef.meta as { fixed?: boolean; flexible?: boolean } | undefined;
    const size = column.getSize();

    if (meta?.fixed) {
      return { flex: `0 0 ${size}px`, minWidth: 0 };
    }
    return { flex: `${size} 1 0`, minWidth: 0 };
  };

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
        <table className="w-full text-sm" style={{ display: 'grid' }}>
          <thead className="bg-slate-700" style={{ display: 'grid', position: 'sticky', top: 0, zIndex: 1 }}>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id} style={{ display: 'flex', width: '100%' }}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-3 py-2 text-left cursor-pointer hover:bg-slate-600 select-none"
                    style={getColumnFlex(header.column)}
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
              display: 'grid',
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
                    display: 'flex',
                    position: 'absolute',
                    transform: `translateY(${virtualRow.start}px)`,
                    width: '100%',
                    height: `${virtualRow.size}px`,
                  }}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td
                      key={cell.id}
                      className="px-3 py-2 border-b border-slate-700 overflow-hidden"
                      style={getColumnFlex(cell.column)}
                    >
                      <div className="truncate" title={String(cell.getValue() ?? '')}>
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext()
                        )}
                      </div>
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
