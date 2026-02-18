# Transform Home Page to Playlist-Builder Style Now-Playing View

## Overview

This plan transforms the Home page from a minimal now-playing display into a full-featured playback view using playlist-builder components (TrackDisplay, WaveformSection, TrackQueueTable). The result is a consistent Obsidian-themed interface with enhanced UX features that reuses existing components without duplication.

**Key changes:**
- Replace simple card layout with builder-style component structure
- Integrate TrackDisplay, WaveformSection, and TrackQueueTable
- Apply Obsidian theme styling (black background, accent borders, SF Mono typography)
- Implement waveform controls (play/pause, loop, auto-advance, seek)
- Enable queue interaction (click to jump to track)
- Add UX enhancements (playlist title, queue position, keyboard shortcuts, loading states)
- Persist loop state across sessions
- Maintain responsive design (desktop table view, mobile cards)

## Enhanced Features (Beyond Original Plan)

Based on improvement analysis, the following features were added:

1. **Playlist Title Display** - Shows actual playlist name (e.g., "Chill Vibes") via React Query cache lookup
2. **Queue Position Indicator** - "Track 3 of 47" display in header for instant orientation
3. **Loop Persistence** - localStorage saves loop toggle state across sessions
4. **Spacebar Play/Pause** - Keyboard shortcut matching standard music app behavior
5. **Click-to-Seek Waveform** - Click anywhere on waveform to jump to position
6. **Loading State** - Spinner during station click → playback transition
7. **Empty Queue Handling** - "No tracks in queue" message for edge cases
8. **Future-Proofing** - Optional `targetDeviceId` parameters for multi-device playback

## Task Sequence

1. [01-refactor-homepage-implementation.md](./01-refactor-homepage-implementation.md) - Complete HomePage refactor with layout, handlers, and all enhanced features
2. [02-manual-testing-verification.md](./02-manual-testing-verification.md) - Comprehensive manual testing including new feature verification

**Note:** Original tasks 02-04 were consolidated. Task 01 now includes handler implementation and empty state styling for better cohesion.

## Success Criteria

### End-to-End Verification

**Visual consistency:**
- ✓ Home page matches PlaylistBuilder aesthetic (Obsidian theme)
- ✓ TrackDisplay shows metadata with accent-colored artist name
- ✓ WaveformSection displays with bordered container and loop toggle
- ✓ TrackQueueTable highlights current track with accent border
- ✓ Loading spinner uses Obsidian accent color

**Functional requirements:**
- ✓ Empty state displays when nothing is playing
- ✓ Station chips launch playback with loading indicator
- ✓ Playlist title shows in header (from cache lookup)
- ✓ Queue position indicator displays "Track X of Y"
- ✓ Waveform plays/pauses on click
- ✓ Click-to-seek works on waveform
- ✓ Loop toggle enables track restart on finish
- ✓ Loop state persists across page refreshes
- ✓ Without loop, tracks auto-advance
- ✓ Clicking queue tracks jumps to that position
- ✓ Spacebar keyboard shortcut toggles play/pause
- ✓ Virtual scrolling works for 100+ track queues

**Responsive behavior:**
- ✓ Desktop: Full table view with all columns
- ✓ Mobile: Card view with sticky player
- ✓ Smooth transitions at breakpoints

**Browser compatibility:**
- ✓ Works in Chrome, Firefox, Safari
- ✓ No console errors or warnings
- ✓ localStorage works across browsers

## Dependencies

### External
- TanStack React Table (already installed)
- TanStack Virtual (already installed)
- Zustand (playerStore - already set up)
- Lucide React (Music icon - already in use)
- React Query (already installed for cache lookup)

### Existing Components (read-only)
- `web/frontend/src/components/builder/TrackDisplay.tsx`
- `web/frontend/src/components/builder/WaveformSection.tsx`
- `web/frontend/src/components/builder/TrackQueueTable.tsx`
- `web/frontend/src/components/WaveformPlayer.tsx`
- `web/frontend/src/components/playlist-builder/TrackQueueCard.tsx`

### Existing Hooks
- `web/frontend/src/hooks/usePlaylists.ts` (for playlist title lookup)

### State Management
- `web/frontend/src/stores/playerStore.ts` (source of truth for playback state)
- `localStorage` (for loop persistence: `music-minion-home-loop`)

## Component Behavior Differences

| Feature | PlaylistBuilder | Home (This Plan) |
|---------|----------------|------------------|
| Actions | Add/Skip buttons | None (read-only) |
| Loop default | `true` (review mode) | `false` (playback, persisted) |
| On finish | Skip or loop | Auto-advance or loop |
| Sorting | Enabled | Disabled (queue order is meaningful) |
| Queue source | Builder hook | playerStore.queue |
| Emoji actions | Enabled | Disabled (omit handler) |
| Keyboard shortcuts | None | Spacebar play/pause |
| Loading states | N/A | Spinner during playback start |
| Position indicator | No | Yes ("Track X of Y") |

## Trade-offs

**Pros:**
- Consistent visual design across builder and playback views
- Component reuse (no duplication)
- Professional Obsidian aesthetic
- Full-featured playback controls
- Enhanced UX with minimal complexity
- Works well on mobile and desktop
- Keyboard shortcuts improve accessibility
- Loading states provide clear feedback
- Loop persistence respects user preferences

**Cons:**
- Larger component (~250 lines vs 110 original)
- More complex than minimal card layout
- Sorting disabled (queue order = playback order)
- No emoji reactions in this view
- Slightly more state management (loop, loading)

## Implementation Notes

### Error Handling
- **Waveform errors**: WaveformPlayer has built-in error UI (red overlay with retry button)
- **Queue table errors**: TanStack React Table is battle-tested and stable
- **No additional error boundaries needed**: Existing infrastructure is sufficient

### Future-Proofing
- Handlers accept optional `targetDeviceId` parameter (unused but ready for multi-device)
- TrackQueueTable row data includes track IDs (ready for drag-to-reorder)

### Performance
- React Query cache lookup: instant (no API calls)
- Virtual scrolling: 60 FPS for 100+ tracks
- localStorage operations: negligible overhead
- Loading state: minimum 500ms to prevent flash

## Future Enhancements

Moved from "nice to have" to "implemented":
- ~~Show playlist name in context title~~ ✓ Implemented (React Query cache)
- ~~Queue position indicator~~ ✓ Implemented ("Track X of Y")
- ~~Persist loop state~~ ✓ Implemented (localStorage)
- ~~Keyboard shortcuts~~ ✓ Implemented (Spacebar)
- ~~Loading states~~ ✓ Implemented (spinner)

Still possible for future iterations:
1. Enable local sorting (visual only, doesn't affect playback queue)
2. Add emoji reactions (pass `onEmojiUpdate` handler to TrackDisplay)
3. Add queue management (remove tracks, reorder via drag-drop)
4. Show "Recently Played" section below queue
5. Display queue statistics (total duration, average rating)
6. Album artwork background gradient effect
7. Mini-visualizer mode (frequency spectrum)
8. Compact mode toggle (hide queue table)

## Quick Start

After implementation:

1. **Run the app**: `music-minion --web`
2. **Test empty state**: Navigate to `/` with no playback
3. **Test playback**: Click a station or play from sidebar
4. **Test features**: Try spacebar, loop toggle, queue clicking, waveform seek
5. **Test persistence**: Enable loop, refresh page, verify it's still enabled

## File Changes Summary

- **Modified**: `web/frontend/src/components/HomePage.tsx` (~110 → ~250 lines)
- **No database changes**
- **No API changes**
- **No new dependencies**
- **Reuses existing components**
