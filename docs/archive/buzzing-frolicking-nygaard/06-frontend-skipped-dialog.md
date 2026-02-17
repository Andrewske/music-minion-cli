---
task: 06-frontend-skipped-dialog
status: done
depends: [05-frontend-review-mode-ui]
files:
  - path: web/frontend/src/components/builder/SkippedTracksDialog.tsx
    action: create
  - path: web/frontend/src/pages/SmartPlaylistEditor.tsx
    action: modify
---

# Frontend: Create and Wire SkippedTracksDialog

## Context
Users need to view and manage skipped tracks - seeing what they've excluded and being able to restore tracks to the playlist. This component doesn't exist yet and needs to be created.

## Files to Modify/Create
- web/frontend/src/components/builder/SkippedTracksDialog.tsx (create)
- web/frontend/src/pages/SmartPlaylistEditor.tsx (modify)

## Implementation Details

### Part 1: Create SkippedTracksDialog Component

Create `web/frontend/src/components/builder/SkippedTracksDialog.tsx`:

```typescript
interface SkippedTracksDialogProps {
  open: boolean;
  onClose: () => void;
  tracks: Track[];
  onUnskip: (trackId: number) => void;
  isUnskipping?: boolean;
}

export function SkippedTracksDialog({
  open,
  onClose,
  tracks,
  onUnskip,
  isUnskipping = false,
}: SkippedTracksDialogProps) {
  // Use Radix Dialog or existing dialog pattern
  // Show list of tracks with title, artist, skipped_at timestamp
  // Each row has "Restore" button that calls onUnskip(track.id)
  // Empty state: "No skipped tracks"
}
```

### Part 2: Wire Dialog in SmartPlaylistEditor

1. **Add dialog state:**
   - `isSkippedDialogOpen: boolean`

2. **Add "View Skipped" button:**
   - Show count: "View Skipped ({skippedTracks.length})"
   - Disabled if count is 0
   - Opens the SkippedTracksDialog

3. **Wire SkippedTracksDialog:**
   - Import new `SkippedTracksDialog` component
   - Pass props:
     - `open={isSkippedDialogOpen}`
     - `onClose={() => setIsSkippedDialogOpen(false)}`
     - `tracks={skippedTracks}`
     - `onUnskip={(trackId) => unskipTrack.mutate(trackId)}`

4. **Handle unskip:**
   - When user clicks unskip in dialog, call `unskipTrack.mutate(trackId)`
   - Track reappears in main list after query invalidation

## Verification
1. Skip several tracks using review mode
2. Exit review mode, click "View Skipped (N)"
3. Verify dialog shows all skipped tracks with title, artist, and timestamp
4. Click "Restore" on one track
5. Verify dialog count decreases and track reappears in main list
6. Verify empty state shows "No skipped tracks" when all are restored
