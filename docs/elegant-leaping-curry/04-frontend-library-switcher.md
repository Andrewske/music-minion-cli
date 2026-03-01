---
task: 04-frontend-library-switcher
status: done
depends:
  - 02-backend-playlist-filtering
files:
  - path: web/frontend/src/stores/libraryStore.ts
    action: create
  - path: web/frontend/src/hooks/usePlaylists.ts
    action: modify
  - path: web/frontend/src/components/sidebar/SidebarLibrarySwitcher.tsx
    action: create
  - path: web/frontend/src/components/sidebar/SidebarPlaylists.tsx
    action: modify
  - path: web/frontend/src/components/tracks/TrackRow.tsx
    action: modify
  - path: web/frontend/src/routes/__root.tsx
    action: modify
---

# Frontend: Library State + Switcher + Streaming Indicator

## Context

The frontend needs to:
1. Track which library is active (local vs soundcloud)
2. Show a dropdown to switch between libraries
3. Indicate which tracks are streaming-only (SC tracks without local files)

Default is "local" - no "All" option, libraries stay strictly separate.

## Files to Modify/Create

- `web/frontend/src/stores/libraryStore.ts` (new)
- `web/frontend/src/hooks/usePlaylists.ts` (modify)
- `web/frontend/src/components/sidebar/SidebarLibrarySwitcher.tsx` (new)
- `web/frontend/src/components/sidebar/SidebarPlaylists.tsx` (modify)
- `web/frontend/src/components/tracks/TrackRow.tsx` (modify - streaming indicator)
- `web/frontend/src/routes/__root.tsx` (modify)

## Implementation Details

### Part 1: libraryStore.ts (new file)

```typescript
import { create } from 'zustand';

type Library = 'local' | 'soundcloud';

interface LibraryState {
  activeLibrary: Library;
  setActiveLibrary: (library: Library) => void;
}

const getInitialLibrary = (): Library => {
  if (typeof window === 'undefined') return 'local';
  const stored = localStorage.getItem('music-minion-library');
  // Default to 'local', only accept 'soundcloud' as valid alternative
  return stored === 'soundcloud' ? 'soundcloud' : 'local';
};

export const useLibraryStore = create<LibraryState>((set) => ({
  activeLibrary: getInitialLibrary(),

  setActiveLibrary: (library) => {
    localStorage.setItem('music-minion-library', library);
    set({ activeLibrary: library });
  },
}));
```

### Part 2: usePlaylists.ts (modify)

Update hook to accept library parameter:

```typescript
import { useQuery } from '@tanstack/react-query';
import type { Playlist } from '../types';

export function usePlaylists(library?: string) {
  return useQuery({
    queryKey: ['playlists', library],  // Include library in cache key
    queryFn: async (): Promise<Playlist[]> => {
      const url = new URL('/api/playlists', window.location.origin);
      if (library) {
        url.searchParams.append('library', library);
      }

      const response = await fetch(url.toString());
      if (!response.ok) {
        throw new Error('Failed to fetch playlists');
      }
      const data = await response.json();
      return data.playlists;
    },
  });
}
```

### Part 3: SidebarLibrarySwitcher.tsx (new file)

```typescript
import { useLibraryStore } from '../../stores/libraryStore';

interface SidebarLibrarySwitcherProps {
  sidebarExpanded: boolean;
}

export function SidebarLibrarySwitcher({ sidebarExpanded }: SidebarLibrarySwitcherProps): JSX.Element | null {
  const { activeLibrary, setActiveLibrary } = useLibraryStore();

  if (!sidebarExpanded) return null;

  return (
    <div className="px-4 py-3 border-b border-obsidian-border">
      <label className="block text-xs text-white/50 uppercase tracking-wider mb-2">
        Library
      </label>
      <select
        value={activeLibrary}
        onChange={(e) => setActiveLibrary(e.target.value as 'local' | 'soundcloud')}
        className="w-full text-sm bg-obsidian-bg text-white border border-obsidian-border rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-obsidian-accent"
      >
        <option value="local">Local Library</option>
        <option value="soundcloud">SoundCloud</option>
      </select>
    </div>
  );
}
```

### Part 4: SidebarPlaylists.tsx (modify)

Add library store consumption:

```typescript
import { useLibraryStore } from '../../stores/libraryStore';
// ... existing imports

export function SidebarPlaylists({ sidebarExpanded }: SidebarPlaylistsProps): JSX.Element {
  const { activeLibrary } = useLibraryStore();
  const { data: playlists, isLoading } = usePlaylists(activeLibrary);  // Pass library

  // ... rest of component unchanged
}
```

### Part 5: TrackRow.tsx (modify - streaming indicator)

Add visual indicator for SC-only tracks (no local file):

```typescript
// In TrackRow component, add streaming indicator:

// Helper to detect streaming-only tracks
const isStreamingOnly = track.source === 'soundcloud' && !track.local_path;

// In the render, near the track title or as a badge:
{isStreamingOnly && (
  <span
    className="ml-2 text-xs text-orange-400/70"
    title="Streaming from SoundCloud"
  >
    ☁️
  </span>
)}
```

Alternative: Use a WiFi/cloud icon instead of emoji for consistency with design system.

### Part 6: __root.tsx (modify)

Add switcher to sidebar children, before SidebarPlaylists:

```typescript
import { SidebarLibrarySwitcher } from './components/sidebar/SidebarLibrarySwitcher';

// In the Sidebar children:
<Sidebar>
  <SidebarLibrarySwitcher sidebarExpanded={sidebarExpanded} />  {/* NEW */}
  <SidebarQuickTag sidebarExpanded={sidebarExpanded} />
  <SidebarPlaylists sidebarExpanded={sidebarExpanded} />
  <SidebarFilters sidebarExpanded={sidebarExpanded} />
</Sidebar>
```

## Verification

1. Start web mode: `music-minion --web`
2. Open sidebar - should see Library dropdown above playlists
3. Default should be "Local Library"
4. Switch to "SoundCloud" - playlist list should update
5. Refresh page - selection should persist
6. SC tracks should show ☁️ indicator
7. Verify `usePlaylists('soundcloud')` makes request to `/api/playlists?library=soundcloud`
