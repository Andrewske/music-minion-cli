---
task: 06-drag-reorder
status: done
depends: [05-sidebar-ui]
files:
  - path: web/frontend/src/components/sidebar/SidebarPlaylists.tsx
    action: modify
---

# Drag-to-Reorder Pinned Playlists

## Context
Add drag-and-drop reordering for pinned playlists using @dnd-kit. This allows users to customize the order of their pinned playlists.

## Files to Modify/Create
- web/frontend/src/components/sidebar/SidebarPlaylists.tsx (modify)

## Implementation Details

**Step 1: Add dnd-kit imports**

```typescript
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
```

**Step 2: Create SortablePlaylistItem wrapper**

```typescript
const SortablePlaylistItem = ({ playlist }: { playlist: Playlist }) => {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
    id: playlist.id,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <PlaylistItem playlist={playlist} isPinned />
    </div>
  );
};
```

**Step 3: Add reorder mutation and DndContext**

```typescript
const reorderMutation = useMutation({
  mutationFn: ({ id, position }: { id: number; position: number }) =>
    reorderPinnedPlaylist(id, position),
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['playlists'] }),
});

const sensors = useSensors(
  useSensor(PointerSensor),
  useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
);

const handleDragEnd = (event: DragEndEvent) => {
  const { active, over } = event;
  if (over && active.id !== over.id) {
    const oldIndex = pinnedPlaylists.findIndex(p => p.id === active.id);
    const newIndex = pinnedPlaylists.findIndex(p => p.id === over.id);
    reorderMutation.mutate({ id: active.id as number, position: newIndex + 1 });
  }
};
```

**Step 4: Wrap pinned section with DndContext**

Replace the pinnedPlaylists.map with:

```typescript
{pinnedPlaylists.length > 0 && (
  <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
    <SortableContext items={pinnedPlaylists.map(p => p.id)} strategy={verticalListSortingStrategy}>
      {pinnedPlaylists.map(playlist => (
        <SortablePlaylistItem key={playlist.id} playlist={playlist} />
      ))}
    </SortableContext>
  </DndContext>
)}
```

**Step 5: Commit**

```bash
git add web/frontend/src/components/sidebar/SidebarPlaylists.tsx
git commit -m "feat: add drag-to-reorder for pinned playlists"
```

## Verification

1. Start the app: `uv run music-minion --web`
2. Pin at least 2 playlists
3. Drag a pinned playlist above/below another pinned playlist
4. Verify the order changes
5. Refresh browser - verify order persists
