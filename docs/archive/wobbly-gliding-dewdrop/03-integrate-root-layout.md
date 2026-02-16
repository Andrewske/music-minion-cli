---
task: 03-integrate-root-layout
status: done
depends: [01-create-sidebar-components, 02-mobile-sidebar]
files:
  - path: web/frontend/src/routes/__root.tsx
    action: modify
---

# Integrate Sidebar into Root Layout

## Context
Replace the current header navigation with the new sidebar. This is the central integration point that makes the sidebar visible across all routes.

## Files to Modify/Create
- `web/frontend/src/routes/__root.tsx` (modify)

## Implementation Details

### Remove Header Navigation
Delete the existing `NavButton` component and `<nav>` element entirely.

### New Layout Structure
```tsx
import { Sidebar } from '../components/sidebar/Sidebar';
import { MobileHeader } from '../components/sidebar/MobileHeader';
import { SidebarPlaylists } from '../components/sidebar/SidebarPlaylists';
import { SidebarFilters } from '../components/sidebar/SidebarFilters';

function RootComponent(): JSX.Element {
  useSyncWebSocket();

  return (
    <div className="flex h-screen bg-black">
      {/* Mobile header - only on small screens */}
      <MobileHeader />

      {/* Desktop sidebar - only on md+ */}
      <div className="hidden md:flex">
        <Sidebar>
          <SidebarPlaylists />
          <SidebarFilters />
        </Sidebar>
      </div>

      {/* Main content area */}
      <main className="flex-1 min-w-0 overflow-y-auto pt-12 md:pt-0 pb-16">
        <Outlet />
      </main>

      {/* Player bar - fixed bottom */}
      <PlayerBar />

      {/* Dev tools */}
      {import.meta.env.DEV && <TanStackRouterDevtools />}
    </div>
  );
}
```

Note: Both `SidebarPlaylists` and `SidebarFilters` are always rendered. They handle their own collapsible state internally. No route-aware switching needed.

### PlayerBar Adjustment
PlayerBar already has `fixed bottom-0 left-0 right-0` - no changes needed.
Main content has `pb-16` to prevent overlap with PlayerBar.

## Verification
1. All routes render with sidebar visible on desktop
2. Mobile shows hamburger, not sidebar
3. PlayerBar renders at bottom on all screen sizes
4. Navigation works via sidebar links
5. No header visible (removed)
