# Compact Comparison UI Implementation Plan

## Overview
Optimize the comparison web UI for height-constrained viewports (720px height on tiled desktop windows). Current non-content space (~330-400px) leaves insufficient room for track cards. Target: ~174px savings through compact header, integrated card buttons, and streamlined player bar.

## Target Viewports
- Desktop tiled 1/4: 1720×720
- Desktop tiled 1/6: 1147×720 or 1720×480
- Mobile Pixel 9: 412×892

## Architecture Decisions

- **Integrated Card Buttons**: Move Archive/Winner buttons into TrackCard component as a bottom row. Eliminates separate TrackActions component and ~64px vertical space. Each card becomes self-contained with its own actions.

- **Equal Height Cards**: Always render metadata fields with placeholder values ("----", "--- BPM", "Unknown genre") to ensure cards are identical height regardless of missing data.

- **Remove QuickSeekBar**: Redundant with waveform click-to-seek functionality. Saves ~20px.

- **Single-Line Header**: Combine session progress and priority path into one compact line. Format: `{folder_name} +{count} [Stats]`

- **Keep Swipe Gestures**: SwipeableTrack wrapper and gesture handling preserved (bug fix out of scope).

## Implementation Tasks

### Phase 1: SessionProgress Component

- [x] Update SessionProgress to accept priorityPath prop and render compact single line
  - Files: `web/frontend/src/components/SessionProgress.tsx` (modify)
  - Changes:
    - Add `priorityPath?: string` to interface
    - Extract folder name from path: `priorityPath?.split('/').filter(Boolean).pop()`
    - Render: `{folderName} +{completed} [Stats button moved to parent]`
    - Use `text-emerald-400 font-mono truncate max-w-[200px]` for folder
    - Use `text-slate-200 font-bold` for count
  - Tests: Component renders with/without priorityPath, truncates long paths
  - Acceptance: Single line output, folder name extracted correctly

### Phase 2: TrackCard Component

- [x] Add action props to TrackCard interface
  - Files: `web/frontend/src/components/TrackCard.tsx` (modify)
  - Changes:
    - Add to interface: `onArchive?: () => void`, `onWinner?: () => void`, `isLoading?: boolean`
  - Acceptance: TypeScript compiles without errors

- [x] Restructure card for integrated buttons and equal heights
  - Files: `web/frontend/src/components/TrackCard.tsx` (modify)
  - Changes:
    - Add `flex flex-col` to card container
    - Wrap main content in `div` with `flex-1` to push actions to bottom
    - Reduce padding: `p-6` → `p-4`
    - Reduce margins: `mb-4` → `mb-2` throughout
    - Reduce play icon: `w-12 h-12` → `w-10 h-10`
  - Acceptance: Card content pushed to top, space for buttons at bottom

- [x] Always render metadata with placeholders for equal height
  - Files: `web/frontend/src/components/TrackCard.tsx` (modify)
  - Changes:
    - Year: `{track.year ?? '----'}`
    - BPM: `{track.bpm ? \`${track.bpm} BPM\` : '--- BPM'}`
    - Genre: `{track.genre ?? 'Unknown genre'}`
    - Add `min-h-[1rem]` to metadata containers
  - Acceptance: Cards with missing metadata same height as cards with full metadata

- [x] Add integrated action button row
  - Files: `web/frontend/src/components/TrackCard.tsx` (modify)
  - Changes:
    - Add at bottom of card (after main content div):
    ```tsx
    {(onArchive && onWinner) && (
      <div className="hidden lg:flex border-t border-slate-800">
        <button
          onClick={(e) => { e.stopPropagation(); onArchive(); }}
          disabled={isLoading}
          className="flex-1 py-2 text-sm font-medium text-rose-400/70 hover:text-rose-400 hover:bg-rose-500/10 transition-colors border-r border-slate-800 disabled:opacity-50"
        >
          🗂️ Archive
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onWinner(); }}
          disabled={isLoading}
          className="flex-1 py-2 text-sm font-medium text-emerald-400/70 hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors disabled:opacity-50"
        >
          🏆 Winner
        </button>
      </div>
    )}
    ```
  - Acceptance: Buttons visible on lg+ screens, muted colors, brighten on hover, disabled during loading

### Phase 3: SwipeableTrack Component

- [x] Add pass-through props for card actions
  - Files: `web/frontend/src/components/SwipeableTrack.tsx` (modify)
  - Changes:
    - Add to interface: `onArchive?: () => void`, `onWinner?: () => void`, `isLoading?: boolean`
    - Pass to TrackCard: `onArchive={onArchive} onWinner={onWinner} isLoading={isLoading}`
  - Acceptance: Props flow from ComparisonView → SwipeableTrack → TrackCard

### Phase 4: ComparisonView Integration

- [x] Update header to compact single line
  - Files: `web/frontend/src/components/ComparisonView.tsx` (modify lines 152-172)
  - Changes:
    - Change `py-3` → `py-2`
    - Pass `priorityPath={priorityPathPrefix ?? undefined}` to SessionProgress
    - Remove separate priority path div (lines 166-170)
    - Smaller Stats button: remove emoji, use `px-3 py-1.5 text-xs`
  - Acceptance: Header ~32px total height, single line

- [x] Wire action props to SwipeableTrack components
  - Files: `web/frontend/src/components/ComparisonView.tsx` (modify lines 177-224)
  - Changes:
    - Remove `flex flex-col gap-4` wrapper divs around SwipeableTrack
    - Remove TrackActions component usage (lines 188-193, 216-221)
    - Add to each SwipeableTrack:
      ```tsx
      onArchive={() => handleSwipeLeft(currentPair.track_X.id)}
      onWinner={() => handleSwipeRight(currentPair.track_X.id)}
      isLoading={isArchiving || isSubmitting}
      ```
  - Acceptance: Clicking integrated buttons triggers same handlers as swipe gestures

- [x] Remove mobile hints section
  - Files: `web/frontend/src/components/ComparisonView.tsx` (modify)
  - Changes: Delete lines 231-236 (entire mobile hints block)
  - Acceptance: No "Swipe Card Right to Win" text rendered

- [x] Streamline player bar
  - Files: `web/frontend/src/components/ComparisonView.tsx` (modify lines 238-273)
  - Changes:
    - Change `p-4 pb-8 lg:pb-4` → `p-3 pb-6 lg:pb-3`
    - Change `gap-2` → `gap-1`
    - Delete QuickSeekBar usage (lines 265-270)
  - Acceptance: Player bar ~100px total, no QuickSeekBar

- [x] Reduce bottom spacer
  - Files: `web/frontend/src/components/ComparisonView.tsx` (modify line 276)
  - Changes: `h-32 lg:h-24` → `h-24 lg:h-20`
  - Acceptance: Spacer clears fixed player bar with minimal excess

- [x] Clean up imports
  - Files: `web/frontend/src/components/ComparisonView.tsx` (modify lines 10-12)
  - Changes:
    - Remove: `import { QuickSeekBar } from './QuickSeekBar';`
    - Remove: `import { TrackActions } from './TrackActions';`
  - Acceptance: No unused imports, build succeeds

### Phase 5: Cleanup

- [x] Delete TrackActions component
  - Files: `web/frontend/src/components/TrackActions.tsx` (delete)
  - Acceptance: File removed, no import errors

- [x] Delete QuickSeekBar component
  - Files: `web/frontend/src/components/QuickSeekBar.tsx` (delete)
  - Acceptance: File removed, no import errors

## Acceptance Criteria

- [x] All comparison controls visible on 720px height viewport without scrolling
- [x] Cards have equal height regardless of missing metadata
- [x] Integrated Archive/Winner buttons work correctly (same behavior as swipe)
- [x] Swipe gestures still functional on mobile
- [x] Loading states disable buttons during operations
- [x] No TypeScript errors (`npm run build`)
- [x] Desktop layout preserved (side-by-side cards at lg+ breakpoint)

## Files to Modify

1. `web/frontend/src/components/SessionProgress.tsx` - compact single line with priorityPath
2. `web/frontend/src/components/TrackCard.tsx` - integrated buttons, equal heights, reduced spacing
3. `web/frontend/src/components/SwipeableTrack.tsx` - pass-through action props
4. `web/frontend/src/components/ComparisonView.tsx` - wire everything together, remove unused components

## Files to Delete

1. `web/frontend/src/components/TrackActions.tsx`
2. `web/frontend/src/components/QuickSeekBar.tsx`

## Dependencies

### Internal
- `../types` - TrackInfo interface (unchanged)
- `../hooks/useSwipeGesture` - swipe handling (unchanged)
- `../stores/comparisonStore` - state management (unchanged)

### External
- React (existing)
- Tailwind CSS (existing)
- @react-spring/web (existing, for SwipeableTrack animations)

## Space Savings Summary

| Component | Before | After | Saved |
|-----------|--------|-------|-------|
| Header | ~50px | ~32px | 18px |
| TrackActions | ~64px | 0px | 64px |
| Mobile hints | ~56px | 0px | 56px |
| Player bar | ~120px | ~100px | 20px |
| Bottom spacer | ~96px | ~80px | 16px |
| **Total** | ~386px | ~212px | **~174px** |

## Out of Scope

- Swipe gesture bug (intermittent failure after several swipes) - debug separately
- Mobile-specific breakpoints - not needed, desktop tiling always above lg breakpoint
- Test file creation - no existing test patterns in this frontend
