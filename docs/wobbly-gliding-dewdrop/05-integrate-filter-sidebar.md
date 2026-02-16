---
task: 05-integrate-filter-sidebar
status: pending
depends: [00-create-filter-store, 03-integrate-root-layout]
files:
  - path: web/frontend/src/components/sidebar/SidebarFilters.tsx
    action: create
  - path: web/frontend/src/components/playlist-builder/FilterSidebar.tsx
    action: modify
  - path: web/frontend/src/components/designs/ObsidianMinimalBuilder.tsx
    action: modify
  - path: web/frontend/src/components/HomePage.tsx
    action: modify
  - path: web/frontend/src/routes/comparison.tsx
    action: modify
  - path: web/frontend/src/routes/history.tsx
    action: modify
---

# Collapsible Global Filters Section

## Context
Create a global filters section in the sidebar that persists across routes. Filter state is stored in Zustand and consumed by multiple pages (Home, Playlist Builder, Comparison, History).

## Files to Modify/Create
- `web/frontend/src/components/sidebar/SidebarFilters.tsx` (new) - wrapper for sidebar
- `web/frontend/src/components/playlist-builder/FilterSidebar.tsx` (modify) - read from store
- `web/frontend/src/components/designs/ObsidianMinimalBuilder.tsx` (modify) - remove inline filters
- `web/frontend/src/components/HomePage.tsx` (modify) - consume filter store
- `web/frontend/src/routes/comparison.tsx` (modify) - consume filter store
- `web/frontend/src/routes/history.tsx` (modify) - consume filter store

## Implementation Details

### SidebarFilters.tsx
Wrapper that renders FilterSidebar inside a collapsible section:
```tsx
import { SidebarSection } from './SidebarSection';
import { FilterSidebar } from '../playlist-builder/FilterSidebar';

interface SidebarFiltersProps {
  sidebarExpanded: boolean;
}

export function SidebarFilters({ sidebarExpanded }: SidebarFiltersProps): JSX.Element {
  return (
    <SidebarSection title="Filters" sidebarExpanded={sidebarExpanded} defaultExpanded={false}>
      <FilterSidebar />
    </SidebarSection>
  );
}
```

### FilterSidebar.tsx Refactor
Remove props, read/write from Zustand store:
```tsx
import { useFilterStore } from '../../stores/filterStore';

export function FilterSidebar(): JSX.Element {
  const { filters, setFilters, toggleConjunction, removeFilter } = useFilterStore();

  const handleUpdate = (newFilters: Filter[]): void => {
    setFilters(newFilters);
  };

  // ... rest of existing UI, but using store state instead of props
}
```

Remove these props entirely:
- `filters` → read from `useFilterStore()`
- `onUpdate` → use `setFilters()` from store
- `isUpdating` → no longer needed (store updates are sync)
- `playlistId` → still needed for genre autocomplete, get from route params

### ObsidianMinimalBuilder.tsx Changes
1. Remove the `<aside>` with FilterSidebar (lines 203-211)
2. Remove `MobileHeader` import and usage (lines 180-187)
3. Remove desktop header with back button (lines 189-198)
4. Main content becomes full width
5. Read filters from store instead of `useBuilderSession`:
   ```tsx
   const { filters } = useFilterStore();
   ```

### Page Integration Pattern
Each page that displays tracks should:
```tsx
import { useFilterStore } from '../stores/filterStore';

function SomePage() {
  const { filters } = useFilterStore();

  // Apply filters to track query
  const filteredTracks = useMemo(() => {
    return tracks.filter(track => applyFilters(track, filters));
  }, [tracks, filters]);
}
```

Or pass filters to API query for server-side filtering.

## Verification
1. Filters section visible in sidebar on all routes
2. Add filter → all track-displaying pages update
3. Navigate between routes → filter state persists
4. Collapse filters section → state preserved
5. Mobile: filters accessible in hamburger sheet
6. Clear filters → all pages show unfiltered tracks
