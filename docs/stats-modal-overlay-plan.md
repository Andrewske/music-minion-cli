# Stats Modal Overlay Implementation Plan

## Overview
Replace the top navigation bar with a stats button that opens a modal overlay. This allows viewing statistics without interrupting audio playback, since the `ComparisonView` component (which contains the audio player) never unmounts.

## Architecture Decisions
- **Modal over Navigation**: Using a modal overlay instead of view switching preserves audio playback state
- **Reuse StatsView content**: Create `StatsModal` as a wrapper that imports existing stats components rather than duplicating code
- **Header placement**: Stats button goes in the comparison header next to `SessionProgress` for easy access
- **Standard modal patterns**: Backdrop click to close, Escape key to close, X button in corner

## Implementation Tasks

### Phase 1: Create Stats Modal Component
- [x] Create `StatsModal.tsx` component
  - Files: `web/frontend/src/components/StatsModal.tsx` (new)
  - Implementation:
    - Full-screen overlay with semi-transparent backdrop (`bg-black/50`)
    - Modal container with max-width and scrollable content
    - Close button (X) in top-right corner
    - Import and render existing `StatsView` components (`StatCard`, `GenreChart`, `Leaderboard`)
    - Use `useStats` hook for data fetching
    - Handle Escape key press to close
    - Handle backdrop click to close
  - Acceptance: Modal renders stats content, closes on X/Escape/backdrop click

### Phase 2: Simplify App.tsx
- [x] Remove navigation bar and view switching
  - Files: `web/frontend/src/App.tsx` (modify)
  - Changes:
    - Remove `useState` for `currentView`
    - Remove nav bar JSX
    - Render only `<ComparisonView />` directly
    - Keep `QueryClientProvider` wrapper
  - Acceptance: App renders ComparisonView without nav bar

### Phase 3: Add Stats Button to ComparisonView
- [x] Add stats button and modal integration
  - Files: `web/frontend/src/components/ComparisonView.tsx` (modify)
  - Changes:
    - Add `useState` for `isStatsOpen`
    - Add stats button (📊 icon) in header div next to `SessionProgress`
    - Import and render `StatsModal` when `isStatsOpen` is true
    - Pass `onClose` callback to toggle modal
  - Acceptance: Button opens modal, modal can be closed, audio continues playing

### Phase 4: Cleanup (Optional)
- [x] Consider removing or keeping `StatsView.tsx`
  - Files: `web/frontend/src/components/StatsView.tsx` (evaluate)
  - Decision: Keep if standalone view might be useful later, or delete if modal fully replaces it
  - Acceptance: No dead code if deleted

## Acceptance Criteria
- [x] Stats button visible in ComparisonView header
- [x] Clicking stats button opens modal with full stats
- [x] Modal closes on: X button, Escape key, backdrop click
- [x] Audio playback continues while stats modal is open
- [x] No TypeScript errors
- [x] Modal is scrollable on mobile devices
- [x] Responsive design maintained

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `web/frontend/src/components/StatsModal.tsx` | Create | Modal wrapper with stats content |
| `web/frontend/src/App.tsx` | Modify | Remove nav bar, render ComparisonView only |
| `web/frontend/src/components/ComparisonView.tsx` | Modify | Add stats button and modal state |
| `web/frontend/src/components/StatsView.tsx` | Keep/Delete | Evaluate after modal complete |

## Dependencies
- Existing `useStats` hook (`web/frontend/src/hooks/useStats.ts`)
- Existing stat components: `StatCard`, `GenreChart`, `Leaderboard`
- Tailwind CSS for styling

## Testing Notes
- Manual test: Start audio playback, open stats modal, verify audio continues
- Manual test: Close modal via all three methods (X, Escape, backdrop)
- Manual test: Verify stats data loads correctly in modal
