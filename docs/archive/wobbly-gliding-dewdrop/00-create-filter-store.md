---
task: 00-create-filter-store
status: done
depends: []
files:
  - path: web/frontend/src/stores/filterStore.ts
    action: create
---

# Create Global Filter Store

## Context
Create a Zustand store for global track filtering. This store will be consumed by multiple routes (Home, Playlist Builder, Comparison, History) to filter displayed tracks.

## Files to Modify/Create
- `web/frontend/src/stores/filterStore.ts` (new)

## Implementation Details

### filterStore.ts
```typescript
import { create } from 'zustand';
import type { Filter } from '../api/builder';

interface FilterState {
  filters: Filter[];
  setFilters: (filters: Filter[]) => void;
  addFilter: (filter: Filter) => void;
  removeFilter: (index: number) => void;
  updateFilter: (index: number, filter: Filter) => void;
  clearFilters: () => void;
  toggleConjunction: (index: number) => void;
}

export const useFilterStore = create<FilterState>((set) => ({
  filters: [],
  setFilters: (filters) => set({ filters }),
  addFilter: (filter) => set((state) => ({
    filters: [...state.filters, filter]
  })),
  removeFilter: (index) => set((state) => ({
    filters: state.filters.filter((_, i) => i !== index)
  })),
  updateFilter: (index, filter) => set((state) => ({
    filters: state.filters.map((f, i) => i === index ? filter : f)
  })),
  clearFilters: () => set({ filters: [] }),
  toggleConjunction: (index) => set((state) => ({
    filters: state.filters.map((f, i) =>
      i === index
        ? { ...f, conjunction: f.conjunction === 'AND' ? 'OR' as const : 'AND' as const }
        : f
    )
  })),
}));
```

### Usage Pattern
Pages that display tracks will:
1. Read `filters` from `useFilterStore()`
2. Apply filters to their track queries (either client-side or via API params)
3. FilterSidebar writes to this store, no props needed

## Verification
1. Import store in a test component
2. Add/remove filters via store actions
3. Verify state updates correctly
