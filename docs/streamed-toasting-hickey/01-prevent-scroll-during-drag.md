---
task: 01-prevent-scroll-during-drag
status: done
depends: []
files:
  - path: web/frontend/src/pages/PlaylistOrganizer.tsx
    action: modify
  - path: web/frontend/src/components/organizer/UnassignedTrackTable.tsx
    action: modify
---

# Prevent Virtual Scrolling During Drag

## Context
When dragging an unassigned track, the virtual scroller recalculates and auto-scrolls to the bottom, creating a jarring UX. This task adds scroll prevention by disabling overflow during active drag operations.

## Files to Modify
- `web/frontend/src/pages/PlaylistOrganizer.tsx` (modify)
- `web/frontend/src/components/organizer/UnassignedTrackTable.tsx` (modify)

## Implementation Details

### Step 1: Pass `isDragging` prop from PlaylistOrganizer to UnassignedTrackTable

In `PlaylistOrganizer.tsx`, locate where `UnassignedTrackTable` is rendered and add the `isDragging` prop:

```tsx
<UnassignedTrackTable
  tracks={unassignedTracks}
  currentTrackId={currentTrack?.id ?? null}
  onTrackClick={playTrack}
  isDragging={activeId !== null && activeDragType === 'unassigned-track'}
/>
```

This calculates `isDragging` based on whether there's an active drag operation for an unassigned track.

### Step 2: Update UnassignedTrackTable to accept `isDragging` prop

In `UnassignedTrackTable.tsx`:

1. Add `isDragging` to the component props interface:
```tsx
interface UnassignedTrackTableProps {
  tracks: PlaylistTrackEntry[];
  currentTrackId: number | null;
  onTrackClick: (trackId: number) => void;
  isDragging?: boolean;  // NEW
}
```

2. Destructure the prop in the component signature:
```tsx
export function UnassignedTrackTable({
  tracks,
  currentTrackId,
  onTrackClick,
  isDragging = false,  // NEW with default
}: UnassignedTrackTableProps): JSX.Element {
```

### Step 3: Disable scroll when dragging

Locate the scroll container div (around line 213) and update its style:

```tsx
<div
  ref={parentRef}
  className="overflow-auto"
  style={{
    maxHeight: '40vh',
    overflow: isDragging ? 'hidden' : 'auto',  // Disable scroll during drag
  }}
>
```

This prevents the virtual scroller from auto-scrolling while a drag is in progress.

## Verification

1. Start the dev server: `music-minion --web`
2. Navigate to a playlist organizer page
3. Scroll the unassigned tracks list to a middle position
4. Start dragging a track
5. **Expected**: The list should NOT scroll to the bottom
6. **Expected**: Scroll position should remain locked during the entire drag operation
7. Drop the track and verify scrolling re-enables
