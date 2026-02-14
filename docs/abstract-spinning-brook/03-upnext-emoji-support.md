---
task: 03-upnext-emoji-support
depends: []
files:
  - path: web/frontend/src/components/UpNext.tsx
    action: modify
---

# Add Emoji Tagging to UpNext

## Context
UpNext shows upcoming tracks in the radio queue. Adding emoji support lets users see and edit tags on queued tracks.

## Files to Modify/Create
- web/frontend/src/components/UpNext.tsx (modify)

## Implementation Details

**Location:** UpNextTrack component (lines 17-33), after duration span

```tsx
<EmojiTrackActions track={track} onUpdate={handleTrackUpdate} compact />
```

**Changes needed:**
1. Import `EmojiTrackActions` component
2. Add `onUpdate` prop to UpNextTrack or use React Query invalidation
3. Add compact emoji actions after duration

**Notes:**
- Track likely has emojis from nowPlaying API response
- Use compact mode for space efficiency
- May need to invalidate `nowPlaying` query on update

## Verification
1. Navigate to radio page (`/`)
2. Check UpNext section on right side
3. Verify emoji badges render for queued tracks
4. Add emoji to upcoming track, confirm it persists
