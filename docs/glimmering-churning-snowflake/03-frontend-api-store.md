---
task: 03-frontend-api-store
status: done
depends:
  - 02-backend-queries-router
files:
  - path: web/frontend/src/api/genres.ts
    action: create
  - path: web/frontend/src/stores/genreStore.ts
    action: create
  - path: web/frontend/src/types/index.ts
    action: modify
---

# Frontend API Client & Zustand Store

## Context
Client-side API layer and state management for genres. Update Track type to include genres array.

## Files to Modify/Create
- `web/frontend/src/api/genres.ts` (new)
- `web/frontend/src/stores/genreStore.ts` (new)
- `web/frontend/src/api/tracks.ts` (modify - Track type)

## Implementation Details

### 1. Create `api/genres.ts`

```typescript
import { apiRequest } from './client';

export interface GenreInfo {
  id: number;
  name: string;
  emoji_id: string | null;
  track_count: number;
  created_at: string;
}

export interface TrackGenre {
  id: number;
  name: string;
  emoji_id: string | null;
  position: number;
}

export async function listGenres(): Promise<GenreInfo[]> {
  return apiRequest<GenreInfo[]>('/genres');
}

export async function renameGenre(genreId: number, name: string): Promise<GenreInfo> {
  return apiRequest<GenreInfo>(`/genres/${genreId}`, {
    method: 'PUT',
    body: JSON.stringify({ name }),
  });
}

export async function assignGenreEmoji(
  genreId: number,
  emojiId: string | null
): Promise<GenreInfo> {
  return apiRequest<GenreInfo>(`/genres/${genreId}/emoji`, {
    method: 'PUT',
    body: JSON.stringify({ emoji_id: emojiId }),
  });
}

export async function deleteGenre(genreId: number): Promise<{ deleted: boolean }> {
  return apiRequest<{ deleted: boolean }>(`/genres/${genreId}`, {
    method: 'DELETE',
  });
}

export async function getTrackGenres(trackId: number): Promise<TrackGenre[]> {
  return apiRequest<TrackGenre[]>(`/tracks/${trackId}/genres`);
}

export async function updateTrackGenres(
  trackId: number,
  genreIds: number[]
): Promise<TrackGenre[]> {
  return apiRequest<TrackGenre[]>(`/tracks/${trackId}/genres`, {
    method: 'PUT',
    body: JSON.stringify({ genre_ids: genreIds }),
  });
}
```

### 2. Create `stores/genreStore.ts`

```typescript
import { create } from 'zustand';
import { listGenres, type GenreInfo } from '../api/genres';

interface GenreState {
  genres: GenreInfo[];
  isLoading: boolean;
  error: string | null;
}

interface GenreActions {
  fetchGenres: () => Promise<void>;
  updateGenre: (updated: GenreInfo) => void;
  removeGenre: (genreId: number) => void;
}

export const useGenreStore = create<GenreState & GenreActions>((set) => ({
  genres: [],
  isLoading: false,
  error: null,

  fetchGenres: async () => {
    set({ isLoading: true, error: null });
    try {
      const genres = await listGenres();
      set({ genres, isLoading: false });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : 'Failed to fetch genres', isLoading: false });
    }
  },

  updateGenre: (updated: GenreInfo) => {
    set((state) => ({
      genres: state.genres.map((g) => (g.id === updated.id ? updated : g)),
    }));
  },

  removeGenre: (genreId: number) => {
    set((state) => ({
      genres: state.genres.filter((g) => g.id !== genreId),
    }));
  },
}));
```

### 3. Update Track type in `api/tracks.ts`

Add to Track interface:
```typescript
export interface Track {
  // ... existing fields
  genre: string | null;  // Keep for backward compat (primary genre from trigger)
  genres: Array<{
    id: number;
    name: string;
    emoji_id: string | null;
    position: number;
  }>;
}
```

Note: The backend tracks endpoint needs to JOIN and include genres. If not already done, update the tracks query to include:
```sql
-- In the tracks endpoint, add genre data
SELECT t.*,
  json_group_array(json_object('id', g.id, 'name', g.name, 'emoji_id', g.emoji_id, 'position', tg.position))
  FILTER (WHERE g.id IS NOT NULL) as genres
FROM tracks t
LEFT JOIN track_genres tg ON t.id = tg.track_id
LEFT JOIN genres g ON tg.genre_id = g.id
GROUP BY t.id
```

## Verification
```bash
cd ~/coding/music-minion-cli/web/frontend
bun run typecheck  # Should pass with new types
```
