---
task: 05-sidebar-ui
status: done
depends: [04-frontend-types-api]
files:
  - path: web/frontend/src/components/sidebar/SidebarPlaylists.tsx
    action: modify
---

# SidebarPlaylists UI

## Context
Update the sidebar to show pinned playlists at the top with pin icons. Add hover interactions to toggle pin state.

## Files to Modify/Create
- web/frontend/src/components/sidebar/SidebarPlaylists.tsx (modify)

## Implementation Details

**Step 1: Add imports**

```typescript
import { Pin } from 'lucide-react';
import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { pinPlaylist, unpinPlaylist, reorderPinnedPlaylist } from '../../api/playlists';
```

**Step 2: Add mutations and split playlists**

Inside component, after existing hooks:
```typescript
const queryClient = useQueryClient();
const [hoveredId, setHoveredId] = useState<number | null>(null);

const pinMutation = useMutation({
  mutationFn: pinPlaylist,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['playlists'] }),
});

const unpinMutation = useMutation({
  mutationFn: unpinPlaylist,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ['playlists'] }),
});

const pinnedPlaylists = playlists?.filter(p => p.pin_order !== null) ?? [];
const unpinnedPlaylists = playlists?.filter(p => p.pin_order === null) ?? [];
```

**Step 3: Create PlaylistItem subcomponent**

```typescript
const PlaylistItem = ({ playlist, isPinned }: { playlist: Playlist; isPinned: boolean }) => {
  const isActive = playlist.id === activePlaylistId;
  const isHovered = hoveredId === playlist.id;

  const handlePinToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isPinned) {
      unpinMutation.mutate(playlist.id);
    } else {
      pinMutation.mutate(playlist.id);
    }
  };

  return (
    <button
      key={playlist.id}
      type="button"
      onClick={() => handlePlaylistClick(playlist.id)}
      onMouseEnter={() => setHoveredId(playlist.id)}
      onMouseLeave={() => setHoveredId(null)}
      className={`w-full flex items-center gap-2 px-3 py-2 rounded transition-colors text-left group
        ${isActive
          ? 'bg-obsidian-accent/10 text-obsidian-accent border-l-2 border-l-obsidian-accent'
          : 'text-white/60 hover:text-white hover:bg-white/5'
        }`}
    >
      <ListMusic className="w-4 h-4 flex-shrink-0" />
      {isPinned && <Pin className="w-3 h-3 flex-shrink-0 text-obsidian-accent" />}
      <span className="truncate text-sm">{playlist.name}</span>
      <span className="ml-auto text-xs text-white/40 flex items-center gap-1">
        {isHovered && (
          <button
            type="button"
            onClick={handlePinToggle}
            className="p-0.5 hover:bg-white/10 rounded"
            title={isPinned ? 'Unpin' : 'Pin to top'}
          >
            <Pin className={`w-3 h-3 ${isPinned ? 'text-obsidian-accent' : 'text-white/40'}`} />
          </button>
        )}
        {playlist.track_count}
      </span>
    </button>
  );
};
```

**Step 4: Update render to show pinned/unpinned sections**

```typescript
return (
  <SidebarSection title="Playlists" sidebarExpanded={sidebarExpanded}>
    <div className="space-y-0.5">
      {isLoading && (
        <div className="px-3 py-2 text-white/30 text-sm">Loading...</div>
      )}
      {pinnedPlaylists.map(playlist => (
        <PlaylistItem key={playlist.id} playlist={playlist} isPinned />
      ))}
      {unpinnedPlaylists.map(playlist => (
        <PlaylistItem key={playlist.id} playlist={playlist} isPinned={false} />
      ))}
    </div>
  </SidebarSection>
);
```

**Step 5: Commit**

```bash
git add web/frontend/src/components/sidebar/SidebarPlaylists.tsx
git commit -m "feat: add pin/unpin UI to sidebar playlists"
```

## Verification

1. Start the app: `uv run music-minion --web`
2. Open browser to http://localhost:5173
3. Hover over a playlist in sidebar - pin icon should appear
4. Click pin icon - playlist should move to top with pin icon visible
5. Click pin icon again - playlist should return to alphabetical position
