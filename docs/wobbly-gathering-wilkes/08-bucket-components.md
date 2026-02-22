---
task: 08-bucket-components
status: pending
depends: [07-organizer-page]
files:
  - path: web/frontend/src/components/organizer/BucketList.tsx
    action: create
  - path: web/frontend/src/components/organizer/Bucket.tsx
    action: create
  - path: web/frontend/src/components/organizer/BucketEditDialog.tsx
    action: create
---

# Bucket UI Components

## Context
Create the bucket list container, individual bucket component with collapsible track list, and edit dialog for bucket name/emoji.

## Files to Modify/Create
- web/frontend/src/components/organizer/BucketList.tsx (new)
- web/frontend/src/components/organizer/Bucket.tsx (new)
- web/frontend/src/components/organizer/BucketEditDialog.tsx (new)

## Implementation Details

### 1. BucketList.tsx

```typescript
import { useState } from 'react';
import { Button } from '../ui/button';
import { Plus } from 'lucide-react';
import Bucket from './Bucket';
import BucketEditDialog from './BucketEditDialog';
import type { Bucket as BucketType } from '../../api/buckets';

interface Track {
  id: number;
  title: string;
  artist?: string;
}

interface Props {
  buckets: BucketType[];
  allTracks: Track[];
  sessionId: string;
  onCreateBucket: (name: string, emojiId?: string) => Promise<BucketType>;
  // Bucket action callbacks from usePlaylistOrganizer
  onMoveBucket: (bucketId: string, direction: 'up' | 'down') => Promise<void>;
  onShuffleBucket: (bucketId: string) => Promise<void>;
  onDeleteBucket: (bucketId: string) => Promise<void>;
  onUpdateBucket: (bucketId: string, updates: { name?: string; emoji_id?: string | null }) => Promise<void>;
  onReorderTracks: (bucketId: string, trackIds: number[]) => Promise<void>;
}

export default function BucketList({
  buckets,
  allTracks,
  sessionId,
  onCreateBucket,
  onMoveBucket,
  onShuffleBucket,
  onDeleteBucket,
  onUpdateBucket,
  onReorderTracks,
}: Props) {
  const [isCreating, setIsCreating] = useState(false);

  const handleCreate = async (name: string, emojiId?: string) => {
    await onCreateBucket(name, emojiId);
    setIsCreating(false);
  };

  // Sort buckets by position
  const sortedBuckets = [...buckets].sort((a, b) => a.position - b.position);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Buckets</h2>
        <Button size="sm" onClick={() => setIsCreating(true)}>
          <Plus className="h-4 w-4 mr-1" />
          Add Bucket
        </Button>
      </div>

      {sortedBuckets.length === 0 && (
        <div className="p-8 border border-dashed rounded-md text-center text-muted-foreground">
          No buckets yet. Create one to start organizing tracks.
        </div>
      )}

      <div className="space-y-2">
        {sortedBuckets.map((bucket, index) => (
          <Bucket
            key={bucket.id}
            bucket={bucket}
            tracks={allTracks.filter((t) => bucket.track_ids.includes(t.id))}
            index={index}
            isFirst={index === 0}
            isLast={index === sortedBuckets.length - 1}
            onMove={(dir) => onMoveBucket(bucket.id, dir)}
            onShuffle={() => onShuffleBucket(bucket.id)}
            onDelete={() => onDeleteBucket(bucket.id)}
            onUpdate={(updates) => onUpdateBucket(bucket.id, updates)}
            onReorderTracks={(trackIds) => onReorderTracks(bucket.id, trackIds)}
          />
        ))}
      </div>

      <BucketEditDialog
        open={isCreating}
        onOpenChange={setIsCreating}
        onSave={handleCreate}
        title="Create Bucket"
      />
    </div>
  );
}
```

### 2. Bucket.tsx

```typescript
import { useState, useCallback } from 'react';
import { ChevronDown, ChevronRight, ArrowUp, ArrowDown, Shuffle, Pencil, Trash2, GripVertical } from 'lucide-react';
import { Button } from '../ui/button';
import { usePlaylistOrganizer } from '../../hooks/usePlaylistOrganizer';
import BucketEditDialog from './BucketEditDialog';
import EmojiDisplay from '../EmojiDisplay';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { Bucket as BucketType } from '../../api/buckets';

interface Track {
  id: number;
  title: string;
  artist?: string;
}

interface Props {
  bucket: BucketType;
  tracks: Track[];
  index: number;
  isFirst: boolean;
  isLast: boolean;
  // Action callbacks from parent (props drilling pattern)
  onMove: (direction: 'up' | 'down') => Promise<void>;
  onShuffle: () => Promise<void>;
  onDelete: () => Promise<void>;
  onUpdate: (updates: { name?: string; emoji_id?: string | null }) => Promise<void>;
  onReorderTracks: (trackIds: number[]) => Promise<void>;
}

function SortableTrackRow({ track }: { track: Track }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
    id: track.id,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-2 px-3 py-2 bg-background border-b last:border-b-0"
    >
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab"
        aria-label="Drag to reorder track"
      >
        <GripVertical className="h-4 w-4 text-muted-foreground" />
      </button>
      <span className="font-medium">{track.title}</span>
      {track.artist && <span className="text-muted-foreground">- {track.artist}</span>}
    </div>
  );
}

export default function Bucket({
  bucket,
  tracks,
  index,
  isFirst,
  isLast,
  onMove,
  onShuffle,
  onDelete,
  onUpdate,
  onReorderTracks,
}: Props) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      if (over && active.id !== over.id) {
        const oldIndex = tracks.findIndex((t) => t.id === active.id);
        const newIndex = tracks.findIndex((t) => t.id === over.id);
        const newOrder = arrayMove(tracks, oldIndex, newIndex).map((t) => t.id);
        onReorderTracks(newOrder);
      }
    },
    [tracks, onReorderTracks]
  );

  const handleSave = async (name: string, emojiId?: string) => {
    await onUpdate({ name, emoji_id: emojiId ?? null });
    setIsEditing(false);
  };

  return (
    <div className="border rounded-md overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 bg-muted">
        {/* Move buttons */}
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          disabled={isFirst}
          onClick={() => onMove('up')}
        >
          <ArrowUp className="h-3 w-3" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6"
          disabled={isLast}
          onClick={() => onMove('down')}
        >
          <ArrowDown className="h-3 w-3" />
        </Button>

        {/* Emoji + Name */}
        <button
          className="flex items-center gap-2 flex-1 text-left"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          {isExpanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
          {bucket.emoji_id && <EmojiDisplay emojiId={bucket.emoji_id} size="md" />}
          <span className="font-medium">{bucket.name}</span>
          <span className="text-muted-foreground">({tracks.length})</span>
        </button>

        {/* Action buttons */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={() => onShuffle()}
            title="Shuffle tracks"
          >
            <Shuffle className="h-3 w-3" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={() => setIsEditing(true)}
            title="Edit bucket"
          >
            <Pencil className="h-3 w-3" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 text-destructive"
            onClick={() => onDelete()}
            title="Delete bucket"
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>

        {/* Keyboard shortcut hint */}
        <span className="text-xs text-muted-foreground">
          Shift+{index < 9 ? index + 1 : 0}
        </span>
      </div>

      {/* Expanded track list */}
      {isExpanded && tracks.length > 0 && (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={tracks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
            <div className="max-h-64 overflow-y-auto">
              {tracks.map((track) => (
                <SortableTrackRow key={track.id} track={track} />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}

      {isExpanded && tracks.length === 0 && (
        <div className="p-4 text-center text-muted-foreground">No tracks in this bucket yet.</div>
      )}

      <BucketEditDialog
        open={isEditing}
        onOpenChange={setIsEditing}
        onSave={handleSave}
        title="Edit Bucket"
        initialName={bucket.name}
        initialEmojiId={bucket.emoji_id ?? undefined}
      />
    </div>
  );
}

// Note: Actions are passed via props from BucketList, which gets them from usePlaylistOrganizer hook.
// This keeps Bucket as a pure presentational component with explicit dependencies.
```

### 3. BucketEditDialog.tsx

```typescript
import { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import EmojiPicker from '../EmojiPicker';
import EmojiDisplay from '../EmojiDisplay';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (name: string, emojiId?: string) => Promise<void>;
  title: string;
  initialName?: string;
  initialEmojiId?: string;
}

export default function BucketEditDialog({
  open,
  onOpenChange,
  onSave,
  title,
  initialName = '',
  initialEmojiId,
}: Props) {
  const [name, setName] = useState(initialName);
  const [emojiId, setEmojiId] = useState<string | undefined>(initialEmojiId);
  const [showEmojiPicker, setShowEmojiPicker] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setName(initialName);
      setEmojiId(initialEmojiId);
    }
  }, [open, initialName, initialEmojiId]);

  const handleSave = async () => {
    if (!name.trim()) return;
    setIsSaving(true);
    try {
      await onSave(name.trim(), emojiId);
    } finally {
      setIsSaving(false);
    }
  };

  const handleEmojiSelect = (emoji: string) => {
    setEmojiId(emoji);
    setShowEmojiPicker(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label htmlFor="bucket-name">Name</Label>
            <Input
              id="bucket-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g., Peak Energy"
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <Label>Emoji (optional)</Label>
            <div className="flex items-center gap-2">
              {emojiId ? (
                <button
                  onClick={() => setShowEmojiPicker(true)}
                  className="p-2 border rounded hover:bg-muted"
                >
                  <EmojiDisplay emojiId={emojiId} size="lg" />
                </button>
              ) : (
                <Button variant="outline" onClick={() => setShowEmojiPicker(true)}>
                  Select Emoji
                </Button>
              )}
              {emojiId && (
                <Button variant="ghost" size="sm" onClick={() => setEmojiId(undefined)}>
                  Remove
                </Button>
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              This emoji will be automatically added to all tracks in this bucket.
            </p>
          </div>

          {showEmojiPicker && (
            <EmojiPicker onSelect={handleEmojiSelect} onClose={() => setShowEmojiPicker(false)} />
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={!name.trim() || isSaving}>
            {isSaving ? 'Saving...' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

## Dependencies
- @dnd-kit/core and @dnd-kit/sortable for drag-and-drop (check if already installed)

## Verification
```bash
# Check dnd-kit is installed
cd web/frontend && npm list @dnd-kit/core

# If not installed:
npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities

# Start dev server
uv run music-minion --web

# Test bucket creation, editing, reordering, deletion
# Test drag-and-drop reordering within expanded bucket
# Test keyboard shortcuts
```
