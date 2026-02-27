---
task: 04-frontend-integration
status: pending
depends: [01-extend-playcontext-schema]
files:
  - path: web/frontend/src/stores/playerStore.ts
    action: modify
  - path: web/frontend/src/pages/PlaylistOrganizer.tsx
    action: modify
---

# Frontend Integration for Organizer Queue

## Context
Update the frontend to use the new "organizer" playback context when playing from the playlist organizer. This switches the queue from loading all playlist tracks to only unassigned tracks, and removes the manual auto-advance logic (now handled by the queue system).

## Files to Modify/Create
- web/frontend/src/stores/playerStore.ts (modify)
- web/frontend/src/pages/PlaylistOrganizer.tsx (modify)

## Implementation Details

### 1. Extend PlayContext Types

**File:** `web/frontend/src/stores/playerStore.ts`

**PlayContext interface** - Add 'organizer' to type union and session_id field:
```typescript
export interface PlayContext {
  type: 'playlist' | 'track' | 'builder' | 'search' | 'comparison' | 'organizer';  // Added 'organizer'
  track_ids?: number[];
  playlist_id?: number;
  builder_id?: number;
  session_id?: string;  // NEW: for organizer context (UUID)
  query?: string;
  start_index?: number;
  shuffle?: boolean;
}
```

### 2. Switch to Organizer Context

**File:** `web/frontend/src/pages/PlaylistOrganizer.tsx`

**At component top** - Import shuffle state from playerStore:
```typescript
// Add to existing imports from playerStore
import { usePlayerStore } from '../stores/playerStore';

// Inside component, add this hook:
const shuffleEnabled = usePlayerStore((state) => state.shuffleEnabled);
```

**Line 122-125** - Modify `handlePlayTrack`:

Replace:
```typescript
play(
  { id: nextTrack.id, title: nextTrack.title, artist: nextTrack.artist },
  { type: 'playlist', playlist_id: playlistId }
)
```

With:
```typescript
play(
  { id: nextTrack.id, title: nextTrack.title, artist: nextTrack.artist },
  {
    type: 'organizer',
    playlist_id: playlistId,
    session_id: session.id,
    shuffle: shuffleEnabled  // Use global shuffle state
  }
)
```

### 3. Remove Manual Auto-Advance Logic

**Lines 115-130** - Remove auto-advance logic:

Delete the entire `playNextUnassignedTrack()` function and its usage. The organizer queue will now automatically advance through unassigned tracks via the backend queue resolution logic.

### 4. Add Auto-Resume Session from localStorage

**File:** `web/frontend/src/pages/PlaylistOrganizer.tsx`

**At component mount** - Check for saved session and auto-resume:

```typescript
// Add useEffect to auto-resume last session
useEffect(() => {
  if (!session && playlistId) {
    // Check localStorage for last session ID for this playlist
    const savedSessionId = localStorage.getItem(`organizer-session-${playlistId}`);
    if (savedSessionId) {
      // Verify session still exists and is active via API
      fetch(`/api/buckets/sessions/${savedSessionId}`)
        .then(res => res.ok ? res.json() : null)
        .then(savedSession => {
          if (savedSession && savedSession.status === 'active') {
            // Auto-resume saved session
            setSession(savedSession);
          } else {
            // Clean up stale localStorage entry
            localStorage.removeItem(`organizer-session-${playlistId}`);
          }
        })
        .catch(() => {
          // Session fetch failed, remove stale entry
          localStorage.removeItem(`organizer-session-${playlistId}`);
        });
    }
  }
}, [playlistId, session]);

// Save session ID when created/resumed
useEffect(() => {
  if (session && playlistId) {
    localStorage.setItem(`organizer-session-${playlistId}`, session.id);
  }
}, [session, playlistId]);
```

**On session apply/discard** - Clean up localStorage:

```typescript
// In handleApplySession or handleDiscardSession:
localStorage.removeItem(`organizer-session-${playlistId}`);
```

This enables seamless multi-session organizing - opening a playlist automatically resumes where you left off, while keeping bucket assignments synced via database across devices.

## Verification
- Run TypeScript type checker: `cd web/frontend && npm run type-check`
- Start dev server: `cd web/frontend && npm run dev`
- Navigate to playlist organizer
- Click play on an unassigned track
- Open browser dev tools → Network tab → WebSocket
- Verify play request includes `context.type: "organizer"` and `context.session_id`
- Verify queue only contains unassigned tracks (inspect state in React DevTools)
- Create organizing session, close tab, reopen playlist → verify session auto-resumes
- Check localStorage in dev tools → verify `organizer-session-{id}` exists
