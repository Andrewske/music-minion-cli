import { useRef, useMemo, useCallback } from 'react';
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
  type Column,
  type Row,
} from '@tanstack/react-table';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useDraggable, useDroppable } from '@dnd-kit/core';
import { GripVertical } from 'lucide-react';
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

  // Make container droppable for bucket tracks
  const { setNodeRef: setDroppableRef, isOver } = useDroppable({
    id: 'unassigned-area',
    data: { type: 'unassigned-area' },
  });

  // Column definitions - memoized to prevent table recalculation on every render
  const columns: ColumnDef<PlaylistTrackEntry>[] = useMemo(() => [
    {
      id: 'drag',
      header: '',
      cell: () => null, // Rendered separately in DraggableRow
      size: 40,
      meta: { fixed: true },
    },
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
      id: 'key_signature',
      accessorKey: 'key_signature',
      header: 'Key',
      cell: (info) => info.getValue() ?? '-',
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
  ], []); // Empty deps - columns definition never changes

  // Helper to get flex style for fixed vs flexible columns - memoized to prevent re-creation
  const getColumnFlex = useCallback((column: Column<PlaylistTrackEntry>): React.CSSProperties => {
    const meta = column.columnDef.meta as { fixed?: boolean; flexible?: boolean } | undefined;
    const size = column.getSize();

    if (meta?.fixed) {
      return { flex: `0 0 ${size}px`, minWidth: 0 };
    }
    return { flex: `${size} 1 0`, minWidth: 0 };
  }, []); // Empty deps - logic never changes

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

  interface DraggableRowProps {
    track: PlaylistTrackEntry;
    virtualRow: { start: number; size: number };
    row: Row<PlaylistTrackEntry>;
    isPlaying: boolean;
    onTrackClick: (trackId: number) => void;
    getColumnFlex: (column: Column<PlaylistTrackEntry>) => React.CSSProperties;
  }

  function DraggableRow({ track, virtualRow, row, isPlaying, onTrackClick, getColumnFlex }: DraggableRowProps): JSX.Element {
    const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
      id: track.id,
      data: { type: 'unassigned-track' },
    });

    // ONLY virtual scrolling transform - drag visuals handled by DragOverlay
    const virtualTransform = `translateY(${virtualRow.start}px)`;

    const rowClasses = `cursor-pointer hover:bg-white/5 transition-colors ${
      isPlaying ? 'bg-obsidian-accent/10 border-l-2 border-l-obsidian-accent' : ''
    }`;

    return (
      <tr
        ref={setNodeRef}
        className={rowClasses}
        onClick={() => onTrackClick(track.id)}
        style={{
          display: 'flex',
          position: 'absolute',
          transform: virtualTransform,
          width: '100%',
          height: `${virtualRow.size}px`,
          opacity: isDragging ? 0 : 1,
        }}
      >
        {/* Drag handle */}
        <td
          className="px-3 py-2 border-b border-obsidian-border/50"
          style={{ flex: '0 0 40px', minWidth: 0 }}
        >
          <div
            {...attributes}
            {...listeners}
            className="cursor-grab active:cursor-grabbing text-white/30 hover:text-white/60 focus:outline-none focus:ring-2 focus:ring-obsidian-accent"
            onClick={(e) => e.stopPropagation()} // Prevent row click when grabbing
            tabIndex={0}
            role="button"
            aria-label={`Drag ${track.title} to assign to bucket`}
          >
            <GripVertical className="w-4 h-4" />
          </div>
        </td>

        {/* Existing cells (filter out drag column by ID, not position) */}
        {row.getVisibleCells()
          .filter(cell => cell.column.id !== 'drag')
          .map((cell) => (
          <td
            key={cell.id}
            className="px-3 py-2 border-b border-obsidian-border/50 overflow-hidden text-white/50"
            style={getColumnFlex(cell.column)}
          >
            <div className="truncate" title={String(cell.getValue() ?? '')}>
              {flexRender(cell.column.columnDef.cell, cell.getContext())}
            </div>
          </td>
        ))}
      </tr>
    );
  }

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
    <div
      ref={setDroppableRef}
      data-testid="unassigned-droppable"
      className={`border border-obsidian-border rounded-lg overflow-hidden ${
        isOver ? 'ring-2 ring-obsidian-accent' : ''
      }`}
    >
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
                  <DraggableRow
                    key={row.id}
                    track={track}
                    virtualRow={virtualRow}
                    row={row}
                    isPlaying={track.id === currentTrackId}
                    onTrackClick={onTrackClick}
                    getColumnFlex={getColumnFlex}
                  />
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
