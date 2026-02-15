# Setup Toast Notifications and Shared Emoji State

## Files to Create
- `web/frontend/src/hooks/useTrackEmojis.ts` (new)
- `web/frontend/src/api/emojis.ts` (new)

## Files to Modify
- `web/frontend/src/main.tsx` (modify - add Toaster component)
- `web/frontend/src/stores/radioStore.ts` (modify - add updateTrackEmojis method)
- `package.json` (add sonner dependency)

## Implementation Details

### Step 1: Install Toast Library

```bash
cd web/frontend
npm install sonner
```

### Step 2: Add Toaster to App Root

Update `web/frontend/src/main.tsx`:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider, createRouter } from '@tanstack/react-router'
import { routeTree } from './routeTree.gen'
import { Toaster } from 'sonner'  // NEW
import './index.css'

const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
    <Toaster position="top-right" richColors />  {/* NEW */}
  </StrictMode>
)
```

### Step 3: Create Emoji API Client

Create `web/frontend/src/api/emojis.ts`:

```typescript
import { apiRequest } from './client';

export interface EmojiInfo {
  emoji_id: string;
  type: 'unicode' | 'custom';
  file_path: string | null;  // Only for custom emojis
  custom_name: string | null;
  default_name: string;
  use_count: number;
  last_used: string | null;
}

export interface TrackEmoji {
  emoji_id: string;
  added_at: string;
}

export async function getTopEmojis(limit: number = 50): Promise<EmojiInfo[]> {
  return apiRequest<EmojiInfo[]>(`/emojis/top?limit=${limit}`);
}

export async function getAllEmojis(limit: number = 100, offset: number = 0): Promise<EmojiInfo[]> {
  return apiRequest<EmojiInfo[]>(`/emojis/all?limit=${limit}&offset=${offset}`);
}

export async function getRecentEmojis(limit: number = 10): Promise<EmojiInfo[]> {
  return apiRequest<EmojiInfo[]>(`/emojis/recent?limit=${limit}`);
}

export async function searchEmojis(query: string): Promise<EmojiInfo[]> {
  return apiRequest<EmojiInfo[]>(`/emojis/search?q=${encodeURIComponent(query)}`);
}

export async function addEmojiToTrack(
  trackId: number,
  emojiId: string
): Promise<{ added: boolean }> {
  return apiRequest<{ added: boolean }>(`/emojis/tracks/${trackId}/emojis`, {
    method: 'POST',
    body: JSON.stringify({ emoji_id: emojiId }),
  });
}

export async function removeEmojiFromTrack(
  trackId: number,
  emojiId: string
): Promise<{ removed: boolean }> {
  return apiRequest<{ removed: boolean }>(
    `/emojis/tracks/${trackId}/emojis/${encodeURIComponent(emojiId)}`,
    { method: 'DELETE' }
  );
}

export async function updateEmojiMetadata(
  emojiId: string,
  customName: string | null
): Promise<{ updated: boolean }> {
  return apiRequest<{ updated: boolean }>(
    `/emojis/metadata/${encodeURIComponent(emojiId)}`,
    {
      method: 'PUT',
      body: JSON.stringify({ custom_name: customName }),
    }
  );
}
```

### Step 4: Create Shared Emoji Hook

Create `web/frontend/src/hooks/useTrackEmojis.ts`:

```typescript
import { useCallback, useState } from 'react';
import { toast } from 'sonner';
import { addEmojiToTrack, removeEmojiFromTrack } from '../api/emojis';

interface TrackWithEmojis {
  id: number;
  emojis?: string[];
}

export interface UseTrackEmojisReturn {
  addEmoji: (emoji: string) => Promise<void>;
  removeEmoji: (emoji: string) => Promise<void>;
  isAdding: boolean;
  isRemoving: boolean;
}

/**
 * Hook for managing track emojis with optimistic updates and error handling.
 * Works with any component that has track data with emojis field.
 *
 * @param track - Current track object
 * @param updateTrack - Function to update track in parent state
 */
export function useTrackEmojis<T extends TrackWithEmojis>(
  track: T | null,
  updateTrack: (updated: T) => void
): UseTrackEmojisReturn {
  const [isAdding, setIsAdding] = useState(false);
  const [isRemoving, setIsRemoving] = useState(false);

  const addEmoji = useCallback(
    async (emoji: string): Promise<void> => {
      if (!track || isAdding) return;

      const previousEmojis = track.emojis || [];

      setIsAdding(true);

      // Optimistic update
      updateTrack({
        ...track,
        emojis: [...previousEmojis, emoji],
      });

      try {
        const result = await addEmojiToTrack(track.id, emoji);
        if (!result.added) {
          // Emoji already existed, revert
          updateTrack({ ...track, emojis: previousEmojis });
        }
      } catch (err) {
        // Rollback on error
        updateTrack({ ...track, emojis: previousEmojis });
        toast.error('Failed to add emoji');
        console.error('Add emoji error:', err);
      } finally {
        setIsAdding(false);
      }
    },
    [track, updateTrack, isAdding]
  );

  const removeEmoji = useCallback(
    async (emoji: string): Promise<void> => {
      if (!track || isRemoving) return;

      const previousEmojis = track.emojis || [];

      setIsRemoving(true);

      // Optimistic update
      updateTrack({
        ...track,
        emojis: previousEmojis.filter((e) => e !== emoji),
      });

      try {
        await removeEmojiFromTrack(track.id, emoji);
      } catch (err) {
        // Rollback on error
        updateTrack({ ...track, emojis: previousEmojis });
        toast.error('Failed to remove emoji');
        console.error('Remove emoji error:', err);
      } finally {
        setIsRemoving(false);
      }
    },
    [track, updateTrack, isRemoving]
  );

  return { addEmoji, removeEmoji, isAdding, isRemoving };
}
```

### Step 5: Update Radio Store

Update `web/frontend/src/stores/radioStore.ts`:

```typescript
interface RadioActions {
  setMuted: (muted: boolean) => void;
  toggleMute: () => void;
  setNowPlaying: (data: NowPlaying | null) => void;
  updateNowPlayingTrack: (track: TrackInfo) => void;  // NEW
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

// In the store implementation, add:
export const useRadioStore = create<RadioStore>((set) => ({
  ...initialState,

  // ... existing methods ...

  updateNowPlayingTrack: (track: TrackInfo) => {
    set((state) => {
      if (!state.nowPlaying) return state;
      return {
        ...state,
        nowPlaying: {
          ...state.nowPlaying,
          track,
        },
      };
    });
  },
}));
```

### Step 6: Update TrackInfo Type

Update `web/frontend/src/api/radio.ts`:

```typescript
export interface TrackInfo {
  id: number;
  title: string | null;
  artist: string | null;
  album: string | null;
  duration: number | null;
  local_path: string | null;
  emojis?: string[];  // NEW
}
```

## Acceptance Criteria
- [ ] `npm install sonner` completes successfully
- [ ] Toaster component appears in browser dev tools
- [ ] Test toast: Add `toast.success('Test')` somewhere, verify it appears top-right
- [ ] useTrackEmojis hook compiles without TypeScript errors
- [ ] radioStore has updateNowPlayingTrack method
- [ ] TrackInfo interface includes emojis field

## Dependencies
- Task 02 (emoji router) - provides API endpoints
- Task 03 (radio API extension) - provides emojis in track data

## Notes

**Why a shared hook?** The `useTrackEmojis` hook can be used in:
- RadioPlayer (now playing track)
- ComparisonView (current comparison track)
- PlaylistBuilder (tracks in builder)
- Any future component showing track info

This ensures consistent emoji behavior and error handling across the entire web interface.
