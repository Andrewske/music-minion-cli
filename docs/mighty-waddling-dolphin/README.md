# Mobile-Friendly Playlist Organizer Improvements

## Overview
Enhance the playlist organizer page for mobile usability while maintaining desktop functionality. This implementation adds:

- **Sticky bucket headers** - Buckets remain visible while scrolling
- **Clickable bucket headers** - One tap/click to assign current track
- **Color-coded visual feedback** - Bucket identity via colored borders
- **Mobile accordion** - Space-efficient collapsed buckets on mobile

**Goal**: Mobile users can organize playlists without relying on drag-and-drop or keyboard shortcuts, while desktop users retain all existing functionality.

## Task Sequence
1. [01-create-color-system.md](./01-create-color-system.md) - Create bucket color palette constants
2. [02-add-bucket-colored-borders.md](./02-add-bucket-colored-borders.md) - Apply colored borders to buckets (left border = inactive, full border = active)
3. [03-sticky-bucket-headers.md](./03-sticky-bucket-headers.md) - Make bucket headers sticky during scroll
4. [04-clickable-bucket-headers.md](./04-clickable-bucket-headers.md) - Enable tap-to-assign on bucket headers
5. [05-mobile-accordion-buckets.md](./05-mobile-accordion-buckets.md) - Implement one-at-a-time expansion on mobile

## Success Criteria

### End-to-End Verification

#### Desktop Testing
1. Start the app: `music-minion --web`
2. Navigate to Playlist Organizer page
3. Play a track from unassigned list
4. Click a bucket header → current track should be assigned to that bucket
5. Bucket containing current track should show full colored border
6. Other buckets should show colored left border only
7. Scroll down → bucket headers stick to top of viewport
8. Keyboard shortcuts (Shift+1-9) should still work
9. Drag-and-drop should still work for all tracks

#### Mobile Testing (resize browser to <768px or use device)
1. Start the app: `music-minion --web`
2. Resize browser window to <768px width or open on mobile device
3. Navigate to Playlist Organizer page
4. All buckets should be collapsed by default
5. Tap expand icon on one bucket → it expands
6. Tap expand icon on different bucket → first bucket collapses, second expands
7. Scroll down → bucket headers stick to top
8. Play a track from unassigned list
9. Tap a bucket header → current track assigned to that bucket

#### Edge Cases
- No current track playing → bucket headers not clickable
- Current track already in bucket → clicking that bucket header does nothing
- Moving track between buckets → works from header click
- Empty buckets → show correct hint text
- 10+ buckets → colors cycle correctly (modulo 10)

### Automated Testing (Optional)
```bash
# Run Playwright tests (if added)
npm run test:e2e -- --grep "playlist organizer mobile"
```

## Dependencies

### Required
- React 18+
- Tailwind CSS (for responsive utilities: `md:`, `hidden`, etc.)
- @dnd-kit (already installed for drag-and-drop)
- lucide-react (for ChevronUp, ChevronDown icons)

### Prerequisites
- Existing playlist organizer functionality working
- Player store (`usePlayerStore`) providing current track state
- Bucket API (`usePlaylistOrganizer` hook) with assignTrack method

## Implementation Notes

### Design Decisions
- **Color palette**: 10 colors cycling by bucket position (not user-configurable in MVP)
- **Auto-apply on arrows**: Mobile selector immediately assigns track (no batch/preview mode)
- **Accordion over tabs**: Simpler implementation, can add swipeable tabs later if desired
- **Desktop unchanged**: All existing functionality (drag-and-drop, keyboard shortcuts) preserved

### Future Enhancements (Post-MVP)
1. Haptic feedback on mobile button taps (`navigator.vibrate`)
2. Swipeable tabs alternative to accordion
3. Bulk selection mode (checkbox + batch assign)
4. Custom bucket colors (user configurable)
5. Drag-to-reorder buckets on mobile
6. Validate color palette for WCAG AA contrast ratios and color-blind accessibility

## Estimated Time
- Task 01: 10 min
- Task 02: 20 min
- Task 03: 10 min
- Task 04: 30 min
- Task 05: 30 min

**Total**: ~1.75 hours
