import { useState, useEffect } from 'react';
import { useDroppable } from '@dnd-kit/core';
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { ChevronDown, ChevronRight, GripVertical, Pencil, Shuffle, Trash2 } from 'lucide-react';
import type { PlaylistTrackEntry } from '../../types';
import type { Bucket } from '../../api/buckets';
import { EmojiDisplay } from '../EmojiDisplay';
import { BucketEditDialog } from './BucketEditDialog';
import { getBucketColor } from '../../constants/bucketColors';

interface BucketComponentProps {
  bucket: Bucket;
  tracks: PlaylistTrackEntry[];
  bucketIndex: number;
  totalBuckets: number;
  currentTrackId: number | null;
  onMove: (direction: 'up' | 'down') => Promise<void>;
  onShuffle: () => Promise<void>;
  onDelete: () => Promise<void>;
  onUpdate: (updates: { name?: string; emoji_id?: string | null }) => Promise<void>;
  onTrackClick: (trackId: number) => void;
  isMobile?: boolean;
  isMobileExpanded?: boolean;
  onMobileToggle?: () => void;
  isActive?: boolean;
  onHeaderClick?: () => void;
  isClickable?: boolean;
}

// Sortable track item component
interface SortableTrackProps {
  track: PlaylistTrackEntry;
  bucketId: string;
  isPlaying: boolean;
  onTrackClick: (trackId: number) => void;
}

function SortableTrack({ track, bucketId, isPlaying, onTrackClick }: SortableTrackProps): JSX.Element {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: track.id,
    data: {
      type: 'bucket-track',
      bucketId,
    },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-2 px-3 py-2 border-b border-obsidian-border/50 last:border-b-0 cursor-pointer ${
        isPlaying
          ? 'bg-obsidian-accent/10 border-l-2 border-l-obsidian-accent'
          : 'bg-obsidian-surface hover:bg-white/5'
      }`}
      onClick={() => onTrackClick(track.id)}
    >
      <div
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing text-white/30 hover:text-white/60"
        onClick={(e) => e.stopPropagation()}
      >
        <GripVertical className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <div className={`text-sm truncate ${isPlaying ? 'text-obsidian-accent font-medium' : 'text-white/90'}`}>
          {track.title}
        </div>
        <div className="text-xs text-white/50 truncate">{track.artist ?? 'Unknown Artist'}</div>
      </div>
    </div>
  );
}

export function BucketComponent({
  bucket,
  tracks,
  bucketIndex,
  totalBuckets,
  currentTrackId,
  onMove,
  onShuffle,
  onDelete,
  onUpdate,
  onTrackClick,
  isMobile = false,
  isMobileExpanded = false,
  onMobileToggle,
  isActive = false,
  onHeaderClick,
  isClickable = false,
}: BucketComponentProps): JSX.Element {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  // Determine actual expanded state based on mobile/desktop mode
  const actuallyExpanded = isMobile ? isMobileExpanded : isExpanded;

  // Handle expand/collapse button click
  const handleToggleExpand = (e: React.MouseEvent): void => {
    e.stopPropagation();
    if (isMobile && onMobileToggle) {
      onMobileToggle();
    } else {
      setIsExpanded(!isExpanded);
    }
  };

  const { setNodeRef: setDropRef, isOver } = useDroppable({
    id: bucket.id,
    data: { type: 'bucket' },
  });

  // Auto-expand on drag hover
  useEffect(() => {
    if (isOver && !actuallyExpanded) {
      const timer = setTimeout(() => {
        if (isMobile && onMobileToggle) {
          onMobileToggle();
        } else {
          setIsExpanded(true);
        }
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [isOver, actuallyExpanded, isMobile, onMobileToggle]);

  // Track IDs for sortable context
  const trackIds = tracks.map((t) => t.id);

  // Keyboard shortcut number (Shift+1 = first bucket)
  const shortcutNumber = bucketIndex < 9 ? bucketIndex + 1 : 0;

  const handleEditSave = async (name: string, emojiId?: string): Promise<void> => {
    await onUpdate({ name, emoji_id: emojiId ?? null });
    setIsEditDialogOpen(false);
  };

  return (
    <div className="bg-obsidian-surface border border-obsidian-border rounded-lg overflow-hidden">
      {/* Header */}
      <div
        ref={setDropRef}
        data-testid={`bucket-header-${bucket.id}`}
        onClick={onHeaderClick}
        className={`flex items-center gap-2 px-3 py-2 transition-colors ${
          isOver ? 'bg-obsidian-accent/20 border-obsidian-accent' : ''
        } ${
          isActive ? 'border-4' : 'border-l-4'
        } ${
          isClickable ? 'cursor-pointer hover:bg-white/5' : ''
        }`}
        style={{
          borderColor: getBucketColor(bucketIndex),
        }}
      >
        {/* Expand/collapse button */}
        <button
          type="button"
          onClick={handleToggleExpand}
          className="text-white/50 hover:text-white/80 transition-colors"
        >
          {actuallyExpanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </button>

        {/* Emoji */}
        {bucket.emoji_id && (
          <EmojiDisplay emojiId={bucket.emoji_id} size="sm" className="shrink-0" />
        )}

        {/* Name and count */}
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-white/90 truncate">
            {bucket.name}
          </span>
          <span className="text-xs text-white/40 ml-2">
            ({tracks.length})
          </span>
        </div>

        {/* Keyboard shortcut badge */}
        <div className="hidden sm:flex items-center gap-1 text-xs text-white/30">
          <kbd className="px-1.5 py-0.5 bg-white/10 rounded">Shift</kbd>
          <span>+</span>
          <kbd className="px-1.5 py-0.5 bg-white/10 rounded">{shortcutNumber}</kbd>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-1">
          {/* Move up */}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onMove('up');
            }}
            disabled={bucketIndex === 0}
            className="p-1.5 text-white/40 hover:text-white/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Move up"
          >
            ↑
          </button>

          {/* Move down */}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onMove('down');
            }}
            disabled={bucketIndex === totalBuckets - 1}
            className="p-1.5 text-white/40 hover:text-white/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Move down"
          >
            ↓
          </button>

          {/* Shuffle */}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onShuffle();
            }}
            disabled={tracks.length < 2}
            className="p-1.5 text-white/40 hover:text-white/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Shuffle tracks"
          >
            <Shuffle className="w-4 h-4" />
          </button>

          {/* Edit */}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setIsEditDialogOpen(true);
            }}
            className="p-1.5 text-white/40 hover:text-white/80 transition-colors"
            title="Edit bucket"
          >
            <Pencil className="w-4 h-4" />
          </button>

          {/* Delete */}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            disabled={tracks.length > 0}
            className="p-1.5 text-white/40 hover:text-red-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title={tracks.length > 0 ? 'Cannot delete bucket with tracks' : 'Delete bucket'}
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Expanded track list */}
      {actuallyExpanded && (
        <div className="border-t border-obsidian-border">
          {tracks.length === 0 ? (
            <div className="px-3 py-4 text-center text-sm text-white/40">
              No tracks assigned. Drag a track here or press Shift+{shortcutNumber}.
            </div>
          ) : (
            <SortableContext
              items={trackIds}
              strategy={verticalListSortingStrategy}
            >
              {tracks.map((track) => (
                <SortableTrack
                  key={track.id}
                  track={track}
                  bucketId={bucket.id}
                  isPlaying={track.id === currentTrackId}
                  onTrackClick={onTrackClick}
                />
              ))}
            </SortableContext>
          )}
        </div>
      )}

      {/* Edit dialog */}
      <BucketEditDialog
        open={isEditDialogOpen}
        onClose={() => setIsEditDialogOpen(false)}
        onSave={handleEditSave}
        mode="edit"
        initialName={bucket.name}
        initialEmojiId={bucket.emoji_id ?? undefined}
      />
    </div>
  );
}
