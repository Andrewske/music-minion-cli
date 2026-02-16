# wobbly-gliding-dewdrop

## Overview

Replace the current header navigation with a collapsible sidebar that:
- Toggles between icons-only (72px) and expanded (280px) views
- Contains navigation, collapsible playlists list, and collapsible global filters
- Uses glade-demo UX patterns with obsidian + green styling

**Key Decisions:**
- Tooltips on hover for collapsed nav icons
- Hamburger menu for mobile (slide-out sheet)
- Both Playlists and Filters sections always visible, independently collapsible
- Global filter store affects all track-displaying routes (Home, Builder, Comparison, History)
- No "back" button needed — playlist selection via sidebar
- Smart playlists shown in list, navigate to their own editor

## Task Sequence

0. [00-create-filter-store.md](./00-create-filter-store.md) - Global Zustand filter store
1. [01-create-sidebar-components.md](./01-create-sidebar-components.md) - Core sidebar UI with nav, toggle, tooltips
2. [02-mobile-sidebar.md](./02-mobile-sidebar.md) - Mobile hamburger + sheet slide-out
3. [03-integrate-root-layout.md](./03-integrate-root-layout.md) - Replace header, wire up layout
4. [04-sidebar-playlists.md](./04-sidebar-playlists.md) - Collapsible playlists section
5. [05-integrate-filter-sidebar.md](./05-integrate-filter-sidebar.md) - Collapsible filters section using store

## Success Criteria

End-to-end verification:
1. **Visual**: Sidebar renders on all routes with obsidian styling
2. **Navigation**: All 6 nav items work, active state highlights
3. **Toggle**: Collapse/expand with smooth 300ms animation
4. **Tooltips**: Hover collapsed icons shows label tooltip (with aria-label for a11y)
5. **Collapsible sections**: Playlists and Filters can expand/collapse independently
6. **Global filters**: Filter state persists across route changes, affects track lists
7. **Mobile**: Hamburger → sheet slide-out works
8. **Persistence**: Sidebar collapse state survives page refresh (localStorage)
9. **PlayerBar**: Fixed bottom, full width, unaffected by sidebar

## Dependencies

- TanStack Router (already in use) for `useLocation()`
- Zustand (already in use) for filter store
- Lucide icons (already in use)
- Radix Dialog (already in use) for Sheet component - reuse existing `ui/sheet.tsx`
- Tailwind CSS with existing obsidian theme variables

## Reference Files

- Current layout: `web/frontend/src/routes/__root.tsx`
- Current home: `web/frontend/src/components/HomePage.tsx`
- Existing filters: `web/frontend/src/components/playlist-builder/FilterSidebar.tsx`
- Existing sheet: `web/frontend/src/components/ui/sheet.tsx`
- UX reference: `~/coding/glade-demo/src/components/icon-rail.tsx`

## Files to Delete

- `web/frontend/src/components/playlist-builder/MobileHeader.tsx` (replaced by global mobile header)
