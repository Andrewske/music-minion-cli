---
task: 03-frontend-state
status: done
depends: [02-backend-api]
files:
  - path: web/frontend/src/types/quicktag.ts
    action: create
  - path: web/frontend/src/stores/quickTagStore.ts
    action: create
---

# Frontend State - Quick Tag Types & Store

## Context
TypeScript interfaces and Zustand store for managing Quick Tag state. The store handles dimension cycling, vote submission, and tracks which dimension is currently displayed.

## Files to Modify/Create
- web/frontend/src/types/quicktag.ts (create)
- web/frontend/src/stores/quickTagStore.ts (create)

## Implementation Details

### 1. TypeScript Interfaces (`types/quicktag.ts`)

```typescript
export interface DimensionPair {
  id: string;
  leftEmoji: string;
  rightEmoji: string;
  label: string;
  description?: string;
  sortOrder: number;
}

export interface TrackDimensionVote {
  dimensionId: string;
  vote: -1 | 0 | 1;
  votedAt: string;
}
```

### 2. Zustand Store (`stores/quickTagStore.ts`)

**State Shape:**
```typescript
interface QuickTagState {
  dimensions: DimensionPair[];
  currentDimensionIndex: number;
  isLoading: boolean;
  error: string | null;

  // Actions
  loadDimensions: () => Promise<void>;
  vote: (trackId: number, vote: -1 | 0 | 1) => Promise<void>;
  nextDimension: () => void;
  prevDimension: () => void;
}
```

**Selector for current dimension (use in components):**
```typescript
// Derive currentDimension via selector - NOT stored in state
const currentDimension = useQuickTagStore(
  s => s.dimensions[s.currentDimensionIndex] ?? null
);
```

**Key Behaviors:**
- `loadDimensions`: Fetch from `/api/quicktag/dimensions`, store in state
- `vote`: POST to `/api/quicktag/vote`, then call `nextDimension()`
- `nextDimension`: Increment index, wrap at end (modulo length)
- `prevDimension`: Decrement index, wrap at start

**Implementation Pattern:**
```typescript
const API_BASE = '/api/quicktag';

loadDimensions: async () => {
  set({ isLoading: true, error: null });
  try {
    const res = await fetch(`${API_BASE}/dimensions`);
    if (!res.ok) throw new Error('Failed to load dimensions');
    const data = await res.json();
    set({ dimensions: data, isLoading: false });
  } catch (err) {
    set({ isLoading: false, error: err instanceof Error ? err.message : 'Unknown error' });
  }
},

vote: async (trackId: number, vote: -1 | 0 | 1) => {
  const { dimensions, currentDimensionIndex } = get();
  const dimension = dimensions[currentDimensionIndex];
  if (!dimension) return;

  try {
    const res = await fetch(`${API_BASE}/vote`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trackId, dimensionId: dimension.id, vote })
    });
    if (!res.ok) throw new Error('Failed to save vote');
    get().nextDimension();
  } catch (err) {
    set({ error: err instanceof Error ? err.message : 'Vote failed' });
  }
}
```

## Verification
1. Import store in browser console or a test component
2. Call `loadDimensions()` and verify dimensions array populated
3. Call `nextDimension()` / `prevDimension()` and verify index cycles correctly
4. Test `vote()` with a track ID and verify API call succeeds
