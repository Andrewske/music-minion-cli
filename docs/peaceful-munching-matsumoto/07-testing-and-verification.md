# Testing and Verification

## Files to Test
- All created components (filterUtils.ts, FilterItem, ConjunctionToggle, FilterEditor, FilterPanel)
- Integration with PlaylistBuilder.tsx
- End-to-end filter workflows

## Manual Testing Checklist

### Basic Operations
- [ ] Add first filter (test all 7 fields: title, artist, album, genre, year, bpm, key)
- [ ] Add second filter with AND conjunction
- [ ] Add third filter with OR conjunction
- [ ] Edit existing filter (change field, operator, value)
- [ ] Delete middle filter (verify conjunction handling)
- [ ] Delete all filters (verify empty state)
- [ ] Clear all filters via button (verify confirmation dialog)

### Validation Tests
- [ ] Try to save filter with empty field → should show error
- [ ] Try to save filter with empty operator → should show error
- [ ] Try to save filter with empty value → should show error
- [ ] Enter non-numeric value for year → should show error "year must be a number"
- [ ] Enter non-numeric value for bpm → should show error "bpm must be a number"
- [ ] Enter decimal for year (e.g., "2024.5") → should show error "Year must be a whole number"
- [ ] Enter decimal for bpm (e.g., "140.5") → should pass (BPM accepts decimals)
- [ ] Enter negative number for year → should show error "year cannot be negative"
- [ ] Enter negative number for bpm → should show error "bpm cannot be negative"

### Field Type Tests
- [ ] Text field + contains operator → verify substring match works
- [ ] Text field + starts_with operator → verify prefix match
- [ ] Text field + ends_with operator → verify suffix match
- [ ] Text field + equals operator → verify exact match
- [ ] Numeric field + gt operator (e.g., year > 2020) → verify greater than
- [ ] Numeric field + gte operator (e.g., bpm >= 140) → verify greater or equal
- [ ] Numeric field + lt operator (e.g., year < 2025) → verify less than
- [ ] Numeric field + lte operator (e.g., bpm <= 150) → verify less or equal

### Genre Dropdown Tests
- [ ] Select genre field + equals operator → verify dropdown appears
- [ ] Select genre from dropdown → verify track counts shown in parentheses
- [ ] Switch to different operator (e.g., contains) → verify dropdown changes to text input
- [ ] Switch to different field → verify input clears and changes

### Conjunction Logic Tests
- [ ] Toggle AND → OR → verify pill changes from gray to blue
- [ ] Toggle OR → AND → verify pill changes from blue to gray
- [ ] Add filter with AND → verify candidates narrow (more restrictive)
- [ ] Change to OR → verify candidates broaden (less restrictive)
- [ ] First filter should have no conjunction toggle above it

### UI/UX Tests
- [ ] Verify edit buttons appear on hover over FilterItem
- [ ] Verify disabled state during mutation (buttons grayed out)
- [ ] Verify loading state during filter update
- [ ] Verify error toast on network failure
- [ ] Verify operator auto-clears when changing field type (e.g., year → title)
- [ ] Verify candidate refresh after filter change
- [ ] Verify smooth transitions and hover states
- [ ] Verify responsive layout (sidebar doesn't break on smaller screens)

### Edge Cases
- [ ] Edit while candidate is loading → verify disabled state
- [ ] Create conflicting filters (e.g., year > 2025 AND year < 2020) → should show "No more candidates"
- [ ] Enter special characters in text values (@#$%^&*) → should work (backend escapes)
- [ ] Delete last filter → verify empty state appears immediately
- [ ] Rapid filter changes → verify no race conditions or duplicate API calls
- [ ] Very long filter values → verify text doesn't overflow container

## End-to-End Test Scenario

**Complete workflow test:**

### Setup
```bash
# Terminal: Start music-minion in web mode
cd ~/coding/music-minion-cli
uv run music-minion --web

# Browser: Navigate to http://localhost:5173
```

### Test Steps

1. **Initial Setup:**
   - [ ] Click "Playlists" in navigation
   - [ ] Create new playlist: "Test Filters"
   - [ ] Click "Build" button
   - [ ] Click "Start Session"
   - [ ] Verify candidate track appears

2. **Add Genre Filter:**
   - [ ] In Filters sidebar, click "+ Add Filter"
   - [ ] Select field: "genre"
   - [ ] Select condition: "equals (=)"
   - [ ] Select genre from dropdown: "dubstep" (or any available genre)
   - [ ] Click "Add Filter"
   - [ ] Verify new candidate is a dubstep track

3. **Add BPM Filter with AND:**
   - [ ] Click "+ Add Filter"
   - [ ] Select field: "bpm"
   - [ ] Select condition: "greater or equal (≥)"
   - [ ] Enter value: "140"
   - [ ] Click "Add Filter"
   - [ ] Verify candidate is dubstep AND >= 140 BPM
   - [ ] Verify "AND" pill appears between filters (gray)

4. **Toggle to OR:**
   - [ ] Click "AND" pill between filters
   - [ ] Verify it changes to "OR" (blue pill)
   - [ ] Verify candidate pool changes (now dubstep OR bpm >= 140)

5. **Edit Filter:**
   - [ ] Hover over first filter (genre)
   - [ ] Click edit icon (pencil ✏️)
   - [ ] Change operator to "contains (~)"
   - [ ] Click "Update Filter"
   - [ ] Verify filter badge updates to show "~" symbol

6. **Delete Filter:**
   - [ ] Hover over second filter (bpm)
   - [ ] Click delete icon (×)
   - [ ] Verify filter removed from list
   - [ ] Verify conjunction toggle disappears (only one filter left)
   - [ ] Verify candidate pool updates

7. **Clear All:**
   - [ ] Click "Clear All" button in header
   - [ ] Verify confirmation dialog appears
   - [ ] Confirm deletion
   - [ ] Verify empty state appears: "No filters active / All tracks are candidates"
   - [ ] Verify candidate changes to any track

8. **Test Validation:**
   - [ ] Click "+ Add Filter"
   - [ ] Select field: "year"
   - [ ] Select condition: "equals (=)"
   - [ ] Enter value: "not-a-number"
   - [ ] Click "Add Filter"
   - [ ] Verify error message appears: "year must be a number"
   - [ ] Enter valid value: "2024"
   - [ ] Verify filter saves successfully
   - [ ] Verify candidate is from 2024

9. **Verify Persistence:**
   - [ ] Close browser tab
   - [ ] Reopen http://localhost:5173/playlists
   - [ ] Navigate to "Test Filters" playlist
   - [ ] Click "Build" button
   - [ ] Verify session resumes with year=2024 filter still active

## Backend Synchronization Verification

**Test filter persistence across UI:**

```bash
# Web UI:
1. Add 2-3 filters in web UI
2. Close browser tab
3. Reopen playlist builder
4. Verify filters are still active

# Blessed CLI:
5. In terminal: music-minion
6. Press 'b' to enter playlist builder mode
7. Select same playlist
8. Press 'f' to view filters
9. Verify same filters appear in CLI
```

## React Query Cache Verification

**Monitor network and cache behavior:**

1. **Open DevTools:**
   - [ ] Open Browser DevTools → Network tab
   - [ ] Filter for "Fetch/XHR" requests

2. **Add a Filter:**
   - [ ] Add filter: genre equals "dubstep"
   - [ ] Verify PUT request to `/api/builder/filters/{playlistId}`
   - [ ] Verify GET request to `/api/builder/candidates/{playlistId}/next`
   - [ ] Verify new track appears (must be dubstep)

3. **React Query DevTools (if installed):**
   - [ ] Open React Query DevTools
   - [ ] Verify `['builder-filters', playlistId]` cache invalidated
   - [ ] Verify `['builder-candidates', playlistId]` cache invalidated
   - [ ] Verify no stale data shown

4. **Loading States:**
   - [ ] Add filter → buttons should disable immediately
   - [ ] Delete filter → buttons should disable
   - [ ] Toggle conjunction → buttons should disable
   - [ ] Verify no duplicate API calls (check Network tab)

5. **Error Handling:**
   - [ ] DevTools → Network → Enable "Offline" mode
   - [ ] Try to add filter
   - [ ] Verify error toast appears: "❌ Failed to update filters..."
   - [ ] Verify filter editor stays open (for retry)
   - [ ] Disable offline mode
   - [ ] Retry save → verify success

## Performance Checks

1. **Filter Update Latency:**
   - [ ] Add filter → should feel instant (< 100ms perceived latency)
   - [ ] React Query optimistic update should show filter immediately
   - [ ] Candidate refresh should occur smoothly in background

2. **Genre Dropdown Population:**
   - [ ] Open genre dropdown
   - [ ] Verify genres appear instantly (extracted from candidates list)
   - [ ] Verify no network request for genre list (check Network tab)
   - [ ] Test with large candidate pool (1000+ tracks) → should still be fast

3. **Memory Leak Check:**
   - [ ] Open DevTools → Memory tab
   - [ ] Take heap snapshot (baseline)
   - [ ] Add/delete filters 20 times
   - [ ] Take another heap snapshot
   - [ ] Compare snapshots → verify no significant growth (< 1MB expected)

## Acceptance Criteria Summary

All tasks pass when:
- [ ] All 7 filter fields work (title, artist, album, genre, year, bpm, key)
- [ ] All text operators work (contains, equals, not_equals, starts_with, ends_with)
- [ ] All numeric operators work (equals, not_equals, gt, gte, lt, lte)
- [ ] Genre dropdown shows track counts
- [ ] Validation prevents invalid filters
- [ ] AND/OR conjunction toggles work
- [ ] Edit/delete operations work
- [ ] Clear all confirmation works
- [ ] Empty state displays correctly
- [ ] Loading states disable interactions
- [ ] Error toasts appear on failures
- [ ] Filters persist across sessions
- [ ] Candidate refresh triggers automatically
- [ ] No console errors
- [ ] No TypeScript errors
- [ ] No visual regressions
- [ ] No memory leaks
- [ ] Performance is acceptable (< 100ms perceived latency)

## Known Limitations (Expected Behavior)

1. **Genre dropdown only shows genres from current candidates:**
   - This is intentional (client-side extraction)
   - If first filter is year >= 2025, genre dropdown only shows 2025+ genres
   - This is acceptable for v1; can add dedicated API endpoint later

2. **No complex boolean expressions:**
   - Cannot express: (genre=dubstep OR genre=trap) AND year >= 2023
   - Only linear AND/OR chain supported
   - This is intentional to keep UI simple

3. **No filter preview before applying:**
   - Filters apply immediately on save (no "preview" mode)
   - This is intentional for instant feedback UX
