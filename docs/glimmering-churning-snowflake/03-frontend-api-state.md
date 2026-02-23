---
task: 03-frontend-api-state
status: pending
depends: [02-genres-api-router]
files:
  - path: web/frontend/src/api/genres.ts
    action: create
  - path: web/frontend/src/stores/genreStore.ts
    action: create
  - path: web/frontend/src/types/index.ts
    action: modify
---

# Frontend API Client & State Management

## Context
TypeScript API client and Zustand store for genre data. Provides the data layer for both the genre selection modal and settings page.

## Files to Modify/Create
- `web/frontend/src/api/genres.ts` (new)
- `web/frontend/src/stores/genreStore.ts` (new)
- `web/frontend/src/types/index.ts` (modify)

## Implementation Details

### API Module: `genres.ts`

Follow pattern from `emojis.ts`:

```typescript
const API_BASE = '/api';

export interface GenreInfo {
  id: number;
  name: string;
  emoji_id: string | null;
  track_count: number;
}

export interface TrackGenre {
  id: number;
  name: string;
  emoji_id: string | null;
  position: number;
}

export async function listGenres(): Promise<GenreInfo[]> {
  const res = await fetch(`${API_BASE}/genres`);
  if (!res.ok) throw new Error('Failed to fetch genres');
  return res.json();
}

export async function renameGenre(genreId: number, name: string): Promise<GenreInfo> {
  const res = await fetch(`${API_BASE}/genres/${genreId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error('Failed to rename genre');
  return res.json();
}

export async function assignGenreEmoji(
  genreId: number,
  emojiId: string | null
): Promise<GenreInfo> {
  const res = await fetch(`${API_BASE}/genres/${genreId}/emoji`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ emoji_id: emojiId }),
  });
  if (!res.ok) throw new Error('Failed to assign emoji');
  return res.json();
}

export async function deleteGenre(genreId: number): Promise<{ deleted: boolean }> {
  const res = await fetch(`${API_BASE}/genres/${genreId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Failed to delete genre');
  return res.json();
}

export async function getTrackGenres(trackId: number): Promise<TrackGenre[]> {
  const res = await fetch(`${API_BASE}/tracks/${trackId}/genres`);
  if (!res.ok) throw new Error('Failed to fetch track genres');
  return res.json();
}

export async function updateTrackGenres(
  trackId: number,
  genreIds: number[]
): Promise<TrackGenre[]> {
  const res = await fetch(`${API_BASE}/tracks/${trackId}/genres`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ genre_ids: genreIds }),
  });
  if (!res.ok) throw new Error('Failed to update track genres');
  return res.json();
}
```

### Zustand Store: `genreStore.ts`

```typescript
import { create } from 'zustand';
import type { GenreInfo } from '../api/genres';
import { listGenres } from '../api/genres';

interface GenreState {
  genres: GenreInfo[];
  isLoading: boolean;
  error: string | null;
  fetchGenres: () => Promise<void>;
  setGenres: (genres: GenreInfo[]) => void;
  updateGenre: (genreId: number, updates: Partial<GenreInfo>) => void;
  removeGenre: (genreId: number) => void;
}

export const useGenreStore = create<GenreState>((set) => ({
  genres: [],
  isLoading: false,
  error: null,

  fetchGenres: async () => {
    set({ isLoading: true, error: null });
    try {
      const genres = await listGenres();
      set({ genres, isLoading: false });
    } catch (err) {
      set({ error: 'Failed to load genres', isLoading: false });
    }
  },

  setGenres: (genres) => set({ genres }),

  updateGenre: (genreId, updates) => set((state) => ({
    genres: state.genres.map((g) =>
      g.id === genreId ? { ...g, ...updates } : g
    ),
  })),

  removeGenre: (genreId) => set((state) => ({
    genres: state.genres.filter((g) => g.id !== genreId),
  })),
}));
```

### Type Updates: `types/index.ts`

Add to existing types:

```typescript
export interface TrackGenre {
  id: number;
  name: string;
  emoji_id: string | null;
  position: number;
}

// Update TrackInfo if needed
export interface TrackInfo {
  // ... existing fields
  genres?: TrackGenre[];  // optional, loaded separately
}
```

## Verification

```typescript
// In browser console or test file:
import { listGenres } from './api/genres';
import { useGenreStore } from './stores/genreStore';

// Test API
const genres = await listGenres();
console.log('Genres:', genres);

// Test store
const store = useGenreStore.getState();
await store.fetchGenres();
console.log('Store genres:', store.genres);
```
