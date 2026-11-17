import { useRef, useCallback, useEffect } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useDraggable } from '@dnd-kit/core';
import type { PlaylistTrackEntry } from '../../types';
import { useIsMobile } from '../../hooks/useIsMobile';
import { TrackRow, TrackRowHeader, TRACK_ROW_HEIGHT } from './TrackRow';

interface UnassignedTrackTableProps {
  tracks: PlaylistTrackEntry[];
  currentTrackId: number | null;
  onTrackClick: (trackId: number) => void;
  isDragging?: boolean;
  noBorder?: boolean;
}

interface DraggableRowProps {
  track: PlaylistTrackEntry;
  start: number;
  isPlaying: boolean;
  onTrackClick: (trackId: number) => void;
}

function DraggableRow({ track, start, isPlaying, onTrackClick }: DraggableRowProps): JSX.Element {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: track.id,
    data: { type: 'unassigned-track' },
  });

  // Only the virtual-scroll transform; drag visuals are handled by DragOverlay
  return (
    <TrackRow
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      aria-label={`${track.title}: click to play, drag to assign to a bucket`}
      track={track}
      isPlaying={isPlaying}
      onPlay={() => onTrackClick(track.id)}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        transform: `translateY(${start}px)`,
        opacity: isDragging ? 0 : undefined,
      }}
    />
  );
}

export function UnassignedTrackTable({
  tracks,
  currentTrackId,
  onTrackClick,
  isDragging = false,
  noBorder = false,
}: UnassignedTrackTableProps): JSX.Element {
  const parentRef = useRef<HTMLDivElement>(null);
  const isMobile = useIsMobile();
  const rowHeight = isMobile ? TRACK_ROW_HEIGHT.mobile : TRACK_ROW_HEIGHT.desktop;

  const getScrollElement = useCallback(() => parentRef.current, []);
  const estimateSize = useCallback(() => rowHeight, [rowHeight]);

  const virtualizer = useVirtualizer({
    count: tracks.length,
    getScrollElement,
    estimateSize,
    overscan: 5,
  });

  // Row height changes across the mobile breakpoint; drop cached measurements
  useEffect(() => {
    virtualizer.measure();
  }, [virtualizer, rowHeight]);

  if (tracks.length === 0) {
    return (
      <div className={`bg-obsidian-surface p-8 text-center ${noBorder ? '' : 'border border-obsidian-border rounded-lg'}`}>
        <div className="text-white/50 text-sm">
          All tracks assigned! Create more buckets or check your assignments.
        </div>
      </div>
    );
  }

  return (
    <div className={`overflow-hidden ${noBorder ? '' : 'border border-obsidian-border rounded-lg'}`}>
      <div
        ref={parentRef}
        style={{ maxHeight: '40vh', overflow: isDragging ? 'hidden' : 'auto' }}
      >
        <div className="sticky top-0 z-20">
          <TrackRowHeader />
        </div>
        <div style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }}>
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const track = tracks[virtualRow.index];
            return (
              <DraggableRow
                key={track.id}
                track={track}
                start={virtualRow.start}
                isPlaying={track.id === currentTrackId}
                onTrackClick={onTrackClick}
              />
            );
          })}
        </div>
      </div>

      <div className="px-3 py-2 border-t border-obsidian-border bg-obsidian-surface text-xs text-white/40">
        {tracks.length} unassigned track{tracks.length !== 1 ? 's' : ''}
      </div>
    </div>
  );
}
