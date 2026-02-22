# mellow-snacking-mochi

## Overview
Wire up the existing "Autoplay" toggle in the comparison page header to control playback behavior when a winner is selected:
- **OFF**: Continue playing the current track (existing behavior)
- **ON (default)**: Immediately start playing track A of the next comparison pair

The toggle UI already exists but was dead code - this task makes it functional.

## Task Sequence
1. [01-add-autoplay-logic.md](./01-add-autoplay-logic.md) - Add auto-play logic to useRecordComparison hook

## Success Criteria
1. Existing "Autoplay" checkbox in comparison header now controls winner playback
2. With toggle OFF: selecting a winner loads next pair but current track continues
3. With toggle ON: selecting a winner loads next pair AND plays track A immediately
4. Toggle state persists across page refreshes (existing localStorage behavior)

## Dependencies
- Existing `AutoplayToggle` component (already in header)
- Existing `autoplay` state in `comparisonStore` (already persisted)
- `usePlayerStore` for playback control
