---
task: 06-organizer-routes
status: pending
depends: [05-organizer-hook]
files:
  - path: web/frontend/src/routes/playlist-organizer/index.tsx
    action: create
  - path: web/frontend/src/routes/playlist-organizer/$playlistId.tsx
    action: create
  - path: web/frontend/src/routes/__root.tsx
    action: modify
  - path: web/frontend/src/components/sidebar/Sidebar.tsx
    action: modify
  - path: web/frontend/src/components/sidebar/SidebarPlaylists.tsx
    action: modify
---

# Frontend Routes for Playlist Organizer

## Context
Create TanStack Router routes for the playlist organizer page, matching the pattern used by playlist-builder. Update sidebar navigation.

## Files to Modify/Create
- web/frontend/src/routes/playlist-organizer/index.tsx (new)
- web/frontend/src/routes/playlist-organizer/$playlistId.tsx (new)
- web/frontend/src/routes/__root.tsx (modify)
- web/frontend/src/components/sidebar/Sidebar.tsx (modify)
- web/frontend/src/components/sidebar/SidebarPlaylists.tsx (modify)

## Implementation Details

### 1. Create index route (`routes/playlist-organizer/index.tsx`)

```typescript
import { createFileRoute, redirect } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { getPlaylists } from '../../api/playlists';

export const Route = createFileRoute('/playlist-organizer/')({
  component: PlaylistOrganizerIndex,
});

function PlaylistOrganizerIndex() {
  const { data: playlists, isLoading } = useQuery({
    queryKey: ['playlists'],
    queryFn: getPlaylists,
  });

  if (isLoading) {
    return <div className="p-4">Loading playlists...</div>;
  }

  if (!playlists?.length) {
    return <div className="p-4">No playlists found. Create a playlist first.</div>;
  }

  // Could redirect to first playlist or show selection
  return (
    <div className="p-4">
      <h1 className="text-xl font-bold mb-4">Playlist Organizer</h1>
      <p className="text-muted-foreground">Select a playlist from the sidebar to start organizing.</p>
    </div>
  );
}
```

### 2. Create playlist route (`routes/playlist-organizer/$playlistId.tsx`)

```typescript
import { createFileRoute } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { getPlaylist } from '../../api/playlists';
import PlaylistOrganizer from '../../pages/PlaylistOrganizer';

export const Route = createFileRoute('/playlist-organizer/$playlistId')({
  component: PlaylistOrganizerRoute,
});

function PlaylistOrganizerRoute() {
  const { playlistId } = Route.useParams();
  const numericId = parseInt(playlistId, 10);

  const { data: playlist, isLoading, error } = useQuery({
    queryKey: ['playlist', numericId],
    queryFn: () => getPlaylist(numericId),
    enabled: !isNaN(numericId),
  });

  if (isLoading) {
    return <div className="p-4">Loading...</div>;
  }

  if (error || !playlist) {
    return <div className="p-4 text-red-500">Playlist not found</div>;
  }

  return (
    <PlaylistOrganizer
      playlistId={numericId}
      playlistName={playlist.name}
      playlistType={playlist.type}
    />
  );
}
```

### 3. Update __root.tsx

Add import for new routes (TanStack Router should auto-discover, but verify).

### 4. Update Sidebar.tsx

Add navigation link for Playlist Organizer below Playlist Builder:

```typescript
// In the navigation section, add:
<SidebarNavItem
  to="/playlist-organizer"
  icon={<Layers className="h-4 w-4" />}
  label="Playlist Organizer"
/>
```

### 5. Update SidebarPlaylists.tsx

Handle organizer route pattern for playlist navigation:

```typescript
// In the click handler for playlist items:
const handlePlaylistClick = (playlistId: number) => {
  const pathname = location.pathname;

  if (pathname.startsWith('/playlist-organizer')) {
    navigate({ to: '/playlist-organizer/$playlistId', params: { playlistId: String(playlistId) } });
  } else if (pathname.startsWith('/playlist-builder')) {
    navigate({ to: '/playlist-builder/$playlistId', params: { playlistId: String(playlistId) } });
  } else if (pathname.startsWith('/comparison')) {
    navigate({ to: '/comparison/$playlistId', params: { playlistId: String(playlistId) } });
  } else {
    // Default to builder
    navigate({ to: '/playlist-builder/$playlistId', params: { playlistId: String(playlistId) } });
  }
};
```

## Verification
```bash
# Start dev server
cd web/frontend && npm run dev

# Navigate to /playlist-organizer in browser
# Should see index page

# Click a playlist in sidebar
# Should navigate to /playlist-organizer/{id}

# Check sidebar shows Playlist Organizer nav item
```
