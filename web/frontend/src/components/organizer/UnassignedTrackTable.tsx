import { useRef } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
  type Column,
} from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { PlaylistTrackEntry } from '../../types';

interface UnassignedTrackTableProps {
  tracks: PlaylistTrackEntry[];
  currentTrackId: number | null;
  onTrackClick: (trackId: number) => void;
}

export function UnassignedTrackTable({
  tracks,
  currentTrackId,
  onTrackClick,
}: UnassignedTrackTableProps): JSX.Element {
  const parentRef = useRef<HTMLDivElement>(null);

  // Column definitions
  const columns: ColumnDef<PlaylistTrackEntry>[] = [
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
      cell: () => '-', // PlaylistTrackEntry doesn't have BPM
      size: 50,
      meta: { fixed: true },
    },
    {
      id: 'key_signature',
      accessorKey: 'key_signature',
      header: 'Key',
      cell: () => '-', // PlaylistTrackEntry doesn't have key
      size: 60,
      meta: { fixed: true },
    },
    {
      id: 'rating',
      accessorKey: 'rating',
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
  const getColumnFlex = (column: Column<PlaylistTrackEntry>): React.CSSProperties => {
    const meta = column.columnDef.meta as { fixed?: boolean; flexible?: boolean } | undefined;
    const size = column.getSize();

    if (meta?.fixed) {
      return { flex: `0 0 ${size}px`, minWidth: 0 };
    }
    return { flex: `${size} 1 0`, minWidth: 0 };
  };

  // TanStack Table setup
  const table = useReactTable({
    data: tracks,
    columns,
    getCoreRowModel: getCoreRowModel(),
    enableSorting: false,
  });

  // Virtual scrolling setup
  const virtualizer = useVirtualizer({
    count: tracks.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 40,
    overscan: 5,
  });

  // Helper to get row highlight classes
  const getRowClasses = (trackId: number): string => {
    const isPlaying = trackId === currentTrackId;

    let classes = 'cursor-pointer hover:bg-white/5 transition-colors ';

    if (isPlaying) {
      classes += 'bg-obsidian-accent/10 border-l-2 border-l-obsidian-accent ';
    }

    return classes;
  };

  if (tracks.length === 0) {
    return (
      <div className="bg-obsidian-surface border border-obsidian-border rounded-lg p-8 text-center">
        <div className="text-white/50 text-sm">
          All tracks assigned! Create more buckets or check your assignments.
        </div>
      </div>
    );
  }

  return (
    <div className="border border-obsidian-border rounded-lg overflow-hidden">
      {/* Desktop: Table view */}
      <div className="hidden md:block">
        <div
          ref={parentRef}
          className="overflow-auto"
          style={{ maxHeight: '40vh' }}
        >
          <table className="w-full text-sm" style={{ display: 'grid' }}>
            <thead
              className="border-b border-obsidian-border bg-obsidian-surface"
              style={{ display: 'grid', position: 'sticky', top: 0, zIndex: 1 }}
            >
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id} style={{ display: 'flex', width: '100%' }}>
                  {headerGroup.headers.map((header) => (
                    <th
                      key={header.id}
                      className="px-3 py-2 text-left text-xs tracking-wider uppercase text-white/30"
                      style={getColumnFlex(header.column)}
                    >
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
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
                    className={getRowClasses(track.id)}
                    onClick={() => onTrackClick(track.id)}
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
                        className="px-3 py-2 border-b border-obsidian-border/50 overflow-hidden text-white/50"
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
      </div>

      {/* Mobile: Card view */}
      <div className="md:hidden max-h-[40vh] overflow-y-auto">
        {tracks.map((track) => (
          <button
            type="button"
            key={track.id}
            className={`w-full text-left px-4 py-3 border-b border-obsidian-border/50 cursor-pointer hover:bg-white/5 ${
              track.id === currentTrackId ? 'bg-obsidian-accent/10' : ''
            }`}
            onClick={() => onTrackClick(track.id)}
          >
            <div className="font-medium text-white/90 truncate">{track.title}</div>
            <div className="text-sm text-white/60 truncate">{track.artist ?? 'Unknown Artist'}</div>
          </button>
        ))}
      </div>

      {/* Track count */}
      <div className="px-3 py-2 border-t border-obsidian-border bg-obsidian-surface text-xs text-white/40">
        {tracks.length} unassigned track{tracks.length !== 1 ? 's' : ''}
      </div>
    </div>
  );
}
