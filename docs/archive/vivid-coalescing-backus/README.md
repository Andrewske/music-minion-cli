# Playlist Builder Track Queue Table

## Overview

Add a sortable track table below the waveform player in the playlist builder, showing all filtered candidates. Users can scroll through the full list, click column headers to sort, and click rows to preview tracks without changing their queue position.

**Key Features:**
- TanStack Table with clickable column headers for server-side sorting
- TanStack Virtual + infinite scroll for smooth loading of large candidate lists
- Dual-highlight system: blue for queue position, green for now-playing track
- Row click previews track without affecting Add/Skip workflow
- Loads 100 tracks at a time, fetches more on scroll

## Task Sequence

1. [01-install-dependencies.md](./01-install-dependencies.md) - Install @tanstack/react-table and @tanstack/react-virtual
2. [02-create-track-queue-table.md](./02-create-track-queue-table.md) - Create virtualized table component with sorting and styling
3. [03-integrate-table-refactor-state.md](./03-integrate-table-refactor-state.md) - Integrate table into PlaylistBuilder, refactor state model, remove SortControl

## Success Criteria

### Manual Testing
- [ ] Start builder session, verify table appears below waveform
- [ ] Click column headers, verify sorting works (ascending/descending toggle)
- [ ] Click a row, verify track plays without advancing queue
- [ ] Click Add/Skip, verify queue advances to next row
- [ ] Scroll through list, verify virtualization (smooth scrolling, no lag)

### Edge Cases
- [ ] Empty candidate list (filters too restrictive) - graceful empty state
- [ ] Single candidate - table works with one row
- [ ] Row click on already-playing track - no-op or minimal state change
- [ ] Sorting while track is playing - track stays playing, table reorders

### Regression
- [ ] Run `npm test` in web/frontend - no test failures
- [ ] Keyboard shortcuts (space for play/pause, 0-9 for seek) still work

## Execution Instructions

1. Execute tasks in numerical order (01 -> 03)
2. Each task file contains:
   - Files to modify/create
   - Implementation details
   - Acceptance criteria
   - Dependencies
3. Verify acceptance criteria before moving to next task

## Dependencies

### External Packages
- `@tanstack/react-table` - Headless table with column header click handling
- `@tanstack/react-virtual` - Virtualized scrolling

### Backend (Modified in Task 03)
- `src/music_minion/domain/playlists/builder.py` - Add sort params to `get_candidate_tracks()`
- `web/backend/routers/builder.py` - Add sort query params to `/candidates/{playlist_id}`

### Existing Code
- `web/frontend/src/api/builder.ts` - Track type definition (modified to pass sort params)
- `web/frontend/src/hooks/useBuilderSession.ts` - Session state management
- `web/frontend/src/pages/PlaylistBuilder.tsx` - Main builder page

### Development Environment
- Node.js with npm
- Existing web/frontend setup with Vite + React + TypeScript
