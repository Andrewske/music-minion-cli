---
task: 02-implement-drag-preview-row
status: done
depends: []
files:
  - path: web/frontend/src/pages/PlaylistOrganizer.tsx
    action: modify
---

# Implement Full-Row Drag Preview Component

## Context
Currently, the DragOverlay shows only simple text during drag operations. This task creates a `DragPreviewRow` component that displays a full table row clone with all columns (drag handle, title, artist, BPM, key, rating), providing rich visual feedback during drags.

## Files to Modify
- `web/frontend/src/pages/PlaylistOrganizer.tsx` (modify)

## Implementation Details

### Step 1: Add necessary imports

At the top of `PlaylistOrganizer.tsx`, ensure you have:
```tsx
import { GripVertical } from 'lucide-react';
import type { PlaylistTrackEntry } from '../types';
```

### Step 2: Create DragPreviewRow component

Add this component definition inside `PlaylistOrganizer.tsx` (before the main component or after, as a separate function):

```tsx
function DragPreviewRow({ track }: { track: PlaylistTrackEntry }): JSX.Element {
  return (
    <div className="bg-obsidian-surface border-2 border-obsidian-accent rounded shadow-2xl cursor-grabbing transform scale-105 opacity-95">
      <div className="flex items-center w-full px-3 py-2 text-sm">
        {/* Drag handle icon */}
        <div className="flex-none w-10 text-white/30">
          <GripVertical className="w-4 h-4" />
        </div>

        {/* Title - flex 3 */}
        <div className="flex-[3] min-w-0 px-2 text-white/90 truncate">
          {track.title}
        </div>

        {/* Artist - flex 2 */}
        <div className="flex-[2] min-w-0 px-2 text-white/70 truncate">
          {track.artist ?? '-'}
        </div>

        {/* BPM - fixed 50px */}
        <div className="flex-none w-[50px] px-2 text-white/60 text-center">
          {track.bpm ? Math.round(track.bpm) : '-'}
        </div>

        {/* Key - fixed 60px */}
        <div className="flex-none w-[60px] px-2 text-white/60 text-center">
          {track.key_signature ?? '-'}
        </div>

        {/* Rating - fixed 70px */}
        <div className="flex-none w-[70px] px-2 text-white/60 text-center">
          {track.rating ? Math.round(track.rating) : '-'}
        </div>
      </div>
    </div>
  );
}
```

**Key styling details**:
- `border-2 border-obsidian-accent`: Prominent accent border for visibility
- `shadow-2xl`: Strong shadow for elevation effect
- `scale-105`: Slight scale increase (5%) to show "lifted" state
- `opacity-95`: Slightly transparent to show it's a preview
- `cursor-grabbing`: Closed fist cursor throughout drag
- Flex values match `UnassignedTrackTable`: title (flex-[3]), artist (flex-[2]), fixed widths for BPM/key/rating

### Step 3: Update trackIdToTrackMap to store full track objects

First, locate the `trackIdToTrackMap` definition (around lines 134-142) and change it to store full `PlaylistTrackEntry` objects:

```tsx
const trackIdToTrackMap = useMemo(() => {
  const map = new Map<number, PlaylistTrackEntry>();
  if (allTracks?.tracks) {
    for (const track of allTracks.tracks) {
      map.set(track.id, track); // Store full track object
    }
  }
  return map;
}, [allTracks]);
```

**Why this change**: The `DragPreviewRow` needs access to all track fields (BPM, key, rating), not just title and artist. Storing the full object is backward compatible since existing code only accesses `.title` and `.artist` which exist on `PlaylistTrackEntry`.

### Step 4: Replace activeTrackDisplay with activeTrack

Locate the `activeTrackDisplay` useMemo (around lines 145-162) and replace it with:

```tsx
// Get full track object for drag preview
const activeTrack = useMemo(() => {
  if (!activeId) return null;
  return trackIdToTrackMap.get(activeId) ?? null;
}, [activeId, trackIdToTrackMap]);
```

**Why this is simpler**:
- Returns the full track object instead of a display string
- No need to differentiate between unassigned/bucket types
- `trackIdToTrackMap` now contains full tracks with all fields
- `DragPreviewRow` needs the full object to render all columns

### Step 5: Update DragOverlay to use DragPreviewRow

Locate the `DragOverlay` component (around lines 481-489) and replace it with:

```tsx
<DragOverlay>
  {activeId && activeTrack ? (
    <DragPreviewRow track={activeTrack} />
  ) : null}
</DragOverlay>
```

**Changes**:
- Use `activeTrack` instead of `activeTrackDisplay`
- Render `DragPreviewRow` component
- Keep default drop animation for smooth visual feedback

## Verification

1. Start dev server: `music-minion --web`
2. Navigate to playlist organizer
3. Start dragging an unassigned track
4. **Expected**: A full-row preview appears under cursor with all columns visible
5. **Expected**: Preview shows drag handle icon, title, artist, BPM, key, rating
6. **Expected**: Preview has elevated styling (shadow, border, slight scale)
7. **Expected**: Preview follows cursor smoothly during drag
8. **Expected**: Column widths in preview match table row columns (visual alignment check)
9. Test bucket-to-bucket drags - same preview should appear
10. Verify all track data displays correctly (handle missing fields gracefully with '-')
11. **Expected**: Default drop animation plays when dropping (smooth transition to final position)
