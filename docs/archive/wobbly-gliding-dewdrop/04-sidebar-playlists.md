---
task: 04-sidebar-playlists
status: done
depends: [01-create-sidebar-components, 03-integrate-root-layout]
files:
  - path: web/frontend/src/components/sidebar/SidebarPlaylists.tsx
    action: create
  - path: web/frontend/src/components/HomePage.tsx
    action: modify
---

# Collapsible Playlists Section in Sidebar

## Context
Playlists currently display in the Home page main content. Move this to a collapsible sidebar section for consistent access across all routes.

## Files to Modify/Create
- `web/frontend/src/components/sidebar/SidebarPlaylists.tsx` (new)
- `web/frontend/src/components/HomePage.tsx` (modify)

## Implementation Details

### SidebarPlaylists.tsx
Collapsible playlist list with active state:
```tsx
import { Link, useParams } from '@tanstack/react-router';
import { ListMusic } from 'lucide-react';
import { usePlaylists } from '../../hooks/usePlaylists';
import { SidebarSection } from './SidebarSection';

interface SidebarPlaylistsProps {
  sidebarExpanded: boolean;
}

export function SidebarPlaylists({ sidebarExpanded }: SidebarPlaylistsProps): JSX.Element {
  const { data: playlists, isLoading } = usePlaylists();
  const params = useParams({ strict: false });
  const activePlaylistId = params.playlistId ? parseInt(params.playlistId, 10) : null;

  return (
    <SidebarSection title="Playlists" sidebarExpanded={sidebarExpanded}>
      <div className="space-y-0.5">
        {isLoading && (
          <div className="px-3 py-2 text-white/30 text-sm">Loading...</div>
        )}
        {playlists?.map(playlist => {
          const isActive = playlist.id === activePlaylistId;
          return (
            <Link
              key={playlist.id}
              to="/playlist-builder/$playlistId"
              params={{ playlistId: String(playlist.id) }}
              className={`flex items-center gap-2 px-3 py-2 rounded transition-colors
                ${isActive
                  ? 'bg-obsidian-accent/10 text-obsidian-accent border-l-2 border-l-obsidian-accent'
                  : 'text-white/60 hover:text-white hover:bg-white/5'
                }`}
            >
              <ListMusic className="w-4 h-4 flex-shrink-0" />
              <span className="truncate text-sm">{playlist.name}</span>
              <span className="ml-auto text-xs text-white/40">
                {playlist.track_count}
              </span>
            </Link>
          );
        })}
      </div>
    </SidebarSection>
  );
}
```

**Features:**
- Shows all playlists (manual and smart)
- Active playlist highlighted with accent border + background
- Collapsible via SidebarSection
- Scrollable content area

### HomePage.tsx Modifications
Remove the playlists grid section entirely (lines ~69-77). Keep:
- Now Playing section
- Stations quick access

The sidebar handles playlist navigation now.

## Verification
1. Navigate to any route - playlists section visible in sidebar
2. Click playlist → navigates to `/playlist-builder/$playlistId`
3. Active playlist highlighted with accent styling
4. Click different playlist → navigation updates, highlight moves
5. Collapse playlists section → chevron rotates, content hides
6. Expand again → content reappears
7. Sidebar scrolls if many playlists
8. Long playlist names truncate properly
9. Smart playlists navigate to SmartPlaylistEditor (existing behavior)
