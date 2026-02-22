import { useState } from 'react';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import type { DragEndEvent } from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { ChevronDown, ChevronRight, GripVertical, Pencil, Shuffle, Trash2 } from 'lucide-react';
import type { PlaylistTrackEntry } from '../../types';
import type { Bucket } from '../../api/buckets';
import { EmojiDisplay } from '../EmojiDisplay';
import { BucketEditDialog } from './BucketEditDialog';

interface BucketComponentProps {
  bucket: Bucket;
  tracks: PlaylistTrackEntry[];
  bucketIndex: number;
  totalBuckets: number;
  onMove: (direction: 'up' | 'down') => Promise<void>;
  onShuffle: () => Promise<void>;
  onDelete: () => Promise<void>;
  onUpdate: (updates: { name?: string; emoji_id?: string | null }) => Promise<void>;
  onReorderTracks: (trackIds: number[]) => Promise<void>;
}

// Sortable track item component
interface SortableTrackProps {
  track: PlaylistTrackEntry;
}

function SortableTrack({ track }: SortableTrackProps): JSX.Element {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: track.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 px-3 py-2 bg-obsidian-surface border-b border-obsidian-border/50 last:border-b-0 hover:bg-white/5"
    >
      <div
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing text-white/30 hover:text-white/60"
      >
        <GripVertical className="w-4 h-4" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm text-white/90 truncate">{track.title}</div>
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
  onMove,
  onShuffle,
  onDelete,
  onUpdate,
  onReorderTracks,
}: BucketComponentProps): JSX.Element {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);

  // DnD sensors
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Track IDs for sortable context
  const trackIds = tracks.map((t) => t.id);

  // Keyboard shortcut number (Shift+1 = first bucket)
  const shortcutNumber = bucketIndex < 9 ? bucketIndex + 1 : 0;

  const handleDragEnd = (event: DragEndEvent): void => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = trackIds.indexOf(active.id as number);
      const newIndex = trackIds.indexOf(over.id as number);
      const newOrder = arrayMove(trackIds, oldIndex, newIndex);
      onReorderTracks(newOrder);
    }
  };

  const handleEditSave = async (name: string, emojiId?: string): Promise<void> => {
    await onUpdate({ name, emoji_id: emojiId ?? null });
    setIsEditDialogOpen(false);
  };

  return (
    <div className="bg-obsidian-surface border border-obsidian-border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2">
        {/* Expand/collapse button */}
        <button
          type="button"
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-white/50 hover:text-white/80 transition-colors"
        >
          {isExpanded ? (
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
            onClick={() => onMove('up')}
            disabled={bucketIndex === 0}
            className="p-1.5 text-white/40 hover:text-white/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Move up"
          >
            ↑
          </button>

          {/* Move down */}
          <button
            type="button"
            onClick={() => onMove('down')}
            disabled={bucketIndex === totalBuckets - 1}
            className="p-1.5 text-white/40 hover:text-white/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Move down"
          >
            ↓
          </button>

          {/* Shuffle */}
          <button
            type="button"
            onClick={onShuffle}
            disabled={tracks.length < 2}
            className="p-1.5 text-white/40 hover:text-white/80 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title="Shuffle tracks"
          >
            <Shuffle className="w-4 h-4" />
          </button>

          {/* Edit */}
          <button
            type="button"
            onClick={() => setIsEditDialogOpen(true)}
            className="p-1.5 text-white/40 hover:text-white/80 transition-colors"
            title="Edit bucket"
          >
            <Pencil className="w-4 h-4" />
          </button>

          {/* Delete */}
          <button
            type="button"
            onClick={onDelete}
            disabled={tracks.length > 0}
            className="p-1.5 text-white/40 hover:text-red-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            title={tracks.length > 0 ? 'Cannot delete bucket with tracks' : 'Delete bucket'}
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Expanded track list */}
      {isExpanded && (
        <div className="border-t border-obsidian-border">
          {tracks.length === 0 ? (
            <div className="px-3 py-4 text-center text-sm text-white/40">
              No tracks assigned. Play a track and press Shift+{shortcutNumber} to assign.
            </div>
          ) : (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={trackIds}
                strategy={verticalListSortingStrategy}
              >
                {tracks.map((track) => (
                  <SortableTrack key={track.id} track={track} />
                ))}
              </SortableContext>
            </DndContext>
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
