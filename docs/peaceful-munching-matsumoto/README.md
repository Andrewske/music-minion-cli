# Playlist Builder Web UI - Filter Section Implementation

## Overview

This implementation adds a fully functional filter UI to the web-based playlist builder, replacing the "Filter UI coming soon" placeholder. The blessed CLI already has a complete 3-step filter wizard; this brings equivalent functionality to the React web frontend.

**What's Being Built:**
- FilterPanel container component with filter list, editor, and state management
- FilterItem component for displaying individual filters
- ConjunctionToggle component for AND/OR logic between filters
- FilterEditor component with 3-step wizard (field → operator → value)
- Validation utilities and helper functions
- Integration with existing React Query hooks and backend API

**Why:**
- Enables web users to filter playlist candidates by metadata fields
- Provides feature parity with blessed CLI filter functionality
- Improves playlist building workflow with real-time candidate filtering

## Task Sequence

1. [01-create-filter-utilities.md](./01-create-filter-utilities.md) - Create validation and helper utilities
2. [02-create-filter-item-component.md](./02-create-filter-item-component.md) - Create filter display component
3. [03-create-conjunction-toggle-component.md](./03-create-conjunction-toggle-component.md) - Create AND/OR toggle button
4. [04-create-filter-editor-component.md](./04-create-filter-editor-component.md) - Create 3-step filter wizard
5. [05-create-filter-panel-container.md](./05-create-filter-panel-container.md) - Create main container component
6. [06-integrate-with-playlist-builder.md](./06-integrate-with-playlist-builder.md) - Wire into PlaylistBuilder page
7. [07-testing-and-verification.md](./07-testing-and-verification.md) - Comprehensive testing checklist

## Success Criteria

### Functional Requirements
- [ ] All 7 filter fields supported (title, artist, album, genre, year, bpm, key)
- [ ] All text operators work (contains, equals, not_equals, starts_with, ends_with)
- [ ] All numeric operators work (equals, not_equals, gt, gte, lt, lte)
- [ ] Genre dropdown shows available genres with track counts
- [ ] AND/OR conjunction toggles between filters
- [ ] Add, edit, delete, and clear all operations work
- [ ] Filters persist across sessions (via backend API)
- [ ] Candidate refresh triggers automatically on filter changes

### Validation
- [ ] Empty field/operator/value prevented
- [ ] Non-numeric values for year/bpm rejected
- [ ] Decimal year rejected (must be integer)
- [ ] Decimal BPM accepted (can be float)
- [ ] Negative numbers rejected
- [ ] Incompatible operator/field combinations prevented

### UI/UX
- [ ] Empty state displays when no filters
- [ ] Edit/delete buttons appear on hover
- [ ] Loading states disable interactions during mutations
- [ ] Error toasts appear for network failures
- [ ] Operator auto-clears when field type changes
- [ ] Smooth transitions and hover states
- [ ] Responsive layout (sidebar doesn't break)

### Performance
- [ ] Filter updates feel instant (< 100ms perceived latency)
- [ ] Genre dropdown populates without network request (client-side extraction)
- [ ] No memory leaks (< 1MB growth after 20+ filter operations)
- [ ] React Query cache invalidation works correctly

## Execution Instructions

1. **Execute tasks in numerical order (01 → 07)**
   - Each task is designed to build on the previous one
   - Do not skip tasks or change order

2. **Each task file contains:**
   - Files to modify/create
   - Implementation details with code examples
   - Acceptance criteria
   - Dependencies on previous tasks

3. **Verify acceptance criteria before moving to next task**
   - Check off all criteria in each task file
   - Run manual tests as specified
   - Fix any issues before proceeding

4. **Final verification (Task 07):**
   - Complete end-to-end test scenario
   - Verify all functional requirements
   - Check performance benchmarks
   - Confirm no regressions

## Architecture Overview

### Component Structure
```
FilterPanel (container)
├── FilterList (display active filters)
│   ├── FilterItem (individual filter with edit/delete)
│   └── ConjunctionToggle (AND/OR between filters)
├── FilterEditor (inline form for add/edit)
│   ├── FieldSelect (step 1: choose field)
│   ├── OperatorSelect (step 2: choose operator based on field type)
│   └── ValueInput (step 3: text input or genre dropdown)
└── EmptyState (when no filters exist)
```

### Key Design Principles
1. **Inline editing** - No modal overlays, edit directly in sidebar
2. **Progressive disclosure** - Show only relevant operators based on field type
3. **Smart defaults** - Genre dropdown when available, text input otherwise
4. **Visual feedback** - Clear AND/OR logic, active filters highlighted
5. **Immediate effect** - Filter updates trigger candidate refresh automatically
6. **Immutable updates** - Replace entire filter array on each change

### Data Flow
```
User Action (add/edit/delete filter)
  ↓
FilterPanel.handleSave/handleDelete/toggleConjunction
  ↓
onUpdate(updatedFilters) → updateFilters.mutate(newFilters)
  ↓
React Query mutation → PUT /api/builder/filters/{playlistId}
  ↓
Backend updates filters in database
  ↓
React Query invalidates cache keys:
  - ['builder-filters', playlistId]
  - ['builder-session', playlistId]
  - ['builder-candidates', playlistId]
  ↓
PlaylistBuilder auto-fetches next candidate
  ↓
New track matching filters appears in UI
```

## Dependencies

### Backend (Already Exists - No Changes Needed)
- **API Endpoints:**
  - `GET /api/builder/filters/{playlistId}` - Fetch filters
  - `PUT /api/builder/filters/{playlistId}` - Update filters
  - `DELETE /api/builder/filters/{playlistId}` - Clear filters
- **Filter Model:** `{ field, operator, value, conjunction }`
- **Supported Fields:** title, artist, album, genre, year, bpm, key
- **Validation:** `src/music_minion/domain/playlists/filters.py`

### Frontend (Already Exists - No Changes Needed)
- **React Query Hooks:** `web/frontend/src/hooks/useBuilderSession.ts`
  - `filters` state
  - `updateFilters` mutation
  - Auto-invalidation of related queries
- **API Client:** `web/frontend/src/api/builder.ts`
  - `getFilters(playlistId)`
  - `updateFilters(playlistId, filters)`
  - `clearFilters(playlistId)`
- **Types:** `Filter` interface in `web/frontend/src/api/builder.ts`

### External Libraries (Already Available)
- React 18+
- TypeScript 5+
- TanStack React Query v5
- Tailwind CSS

## Files Created by This Implementation

### New Files (5 total, ~600 lines)
1. `web/frontend/src/components/builder/filterUtils.ts` - Utilities (50-70 lines)
2. `web/frontend/src/components/builder/FilterItem.tsx` - Display component (40-60 lines)
3. `web/frontend/src/components/builder/ConjunctionToggle.tsx` - AND/OR button (20-30 lines)
4. `web/frontend/src/components/builder/FilterEditor.tsx` - 3-step wizard (200-250 lines)
5. `web/frontend/src/components/builder/FilterPanel.tsx` - Container (150-200 lines)

### Modified Files (1 total)
1. `web/frontend/src/pages/PlaylistBuilder.tsx` - Integration (lines 150-157, remove 228-235)

## Design Decisions & Trade-offs

### Genre Dropdown: Client-Side Extraction
**Decision:** Extract genres from current candidates list (client-side) rather than creating new API endpoint.

**Pros:**
- No backend changes required
- Works immediately
- No additional network request

**Cons:**
- Only shows genres present in current candidate pool (after filtering)

**Rationale:** Start simple, add dedicated `/api/library/genres` endpoint later if needed.

### Inline Editor vs Modal
**Decision:** Use inline editor that replaces "Add Filter" button, not a modal overlay.

**Pros:**
- Simpler implementation (no modal z-index issues)
- Consistent with blessed CLI's inline editor

**Cons:**
- Takes up more vertical space when editing

**Rationale:** Sidebar is underutilized, so space is available.

### Immediate Effect vs Apply Button
**Decision:** Filter changes apply immediately (no "Apply" button), triggering candidate refresh.

**Pros:**
- Instant feedback
- Matches blessed CLI behavior
- React Query handles optimistic updates well

**Cons:**
- Rapid changes could cause many API calls

**Rationale:** React Query's mutation queue handles rapid changes gracefully.

### AND-only Logic (No Complex Boolean Expressions)
**Decision:** Support only AND/OR between adjacent filters (linear chain), no grouping or parentheses.

**Pros:**
- Simple UI (no parentheses or grouping UI needed)
- Covers 95% of use cases

**Cons:**
- Can't express: (genre=dubstep OR genre=trap) AND year >= 2023

**Rationale:** Complexity not worth it for rare use cases.

## Future Enhancements (Out of Scope)

These are explicitly NOT included but could be added later:
1. Dedicated Genre API endpoint for full library genres
2. Filter presets (save/load common combinations)
3. Filter groups with parentheses
4. Autocomplete for text fields
5. Recent values memory
6. Drag-to-reorder filters
7. Filter templates ("More like this" button)
8. Advanced operators (regex, date ranges, multi-select)
9. Filter statistics (preview candidate count)
10. Keyboard shortcuts (f to add, Esc to cancel)

## Estimated Effort

- **Task 01-03 (foundation components):** 1-2 hours
- **Task 04 (filter editor):** 2-3 hours
- **Task 05 (filter panel):** 1-2 hours
- **Task 06 (integration):** 30 minutes
- **Task 07 (testing):** 1-2 hours
- **Total:** 5-7 hours

## Support & Troubleshooting

### Common Issues

**Issue:** Genre dropdown is empty
- **Cause:** No candidates loaded yet or no genres in current pool
- **Fix:** Ensure candidates are loaded; check Network tab for `/api/builder/candidates/next`

**Issue:** Filters don't persist after refresh
- **Cause:** API not saving filters or session lost
- **Fix:** Check Network tab for PUT request to `/api/builder/filters/{playlistId}`; verify backend logs

**Issue:** Candidate doesn't refresh after filter change
- **Cause:** React Query cache not invalidating
- **Fix:** Check `useBuilderSession.ts` lines 86-90 for invalidation logic

**Issue:** TypeScript errors on Filter type
- **Cause:** Import path incorrect
- **Fix:** Ensure `import type { Filter } from '../../api/builder'` (relative path correct)

**Issue:** Buttons stay disabled after mutation
- **Cause:** isUpdating prop not resetting
- **Fix:** Check `updateFilters.isPending` value; verify mutation completes

### Debug Checklist
- [ ] Check browser console for errors
- [ ] Check Network tab for API requests
- [ ] Verify React Query DevTools shows cache invalidation
- [ ] Check backend logs for filter validation errors
- [ ] Verify blessed CLI shows same filters (persistence check)

## Reference Documentation

- **Original Plan:** `.claude/plans/peaceful-munching-matsumoto.md`
- **Backend Validation:** `src/music_minion/domain/playlists/filters.py`
- **Frontend Hooks:** `web/frontend/src/hooks/useBuilderSession.ts`
- **API Client:** `web/frontend/src/api/builder.ts`
- **Type Definitions:** `Filter` interface in `web/frontend/src/api/builder.ts`
