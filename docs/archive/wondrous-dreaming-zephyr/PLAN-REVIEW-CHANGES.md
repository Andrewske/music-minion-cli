# Plan Review Changes - Applied February 2026

This document summarizes all changes made to the emoji reaction system plan based on comprehensive code review and analysis.

## Final Review Changes (Opus 4.5 - February 13, 2026)

### Applied Changes

1. **Combined v31 and v32 migrations** - All custom emoji support (type, file_path columns, custom_emojis directory) now in single v31 migration

2. **Added auto-create logic to bulk-tag script** - Script now auto-creates emoji_metadata for unknown Unicode emojis (matching web UI behavior)

3. **Removed "custom:" prefix** - Custom emojis use UUID only in emoji_id, type column distinguishes custom vs unicode

4. **Deleted stale 10-custom-emoji-upload.md** - Only CLI script approach remains

5. **Added type/file_path to all backend queries** - All SELECT statements and EmojiInfo model now include these fields

6. **Removed unnecessary track_emojis.id column** - Using composite PRIMARY KEY (track_id, emoji_id)

7. **Added variation selector stripping** - normalize_emoji_id() now strips U+FE0E and U+FE0F for consistent storage

8. **Switched to emoji-mart library** - Replaced custom EmojiPicker implementation with emoji-mart, eliminating ~300 lines of custom code while gaining battle-tested keyboard navigation, accessibility, skin tone support, and built-in emoji data

---

## Critical Issues Fixed

### 1. N+1 Query Problem (CRITICAL)
**Problem:** Track list endpoints would execute 1 + N queries (one for tracks, one per track for emojis).

**Solution:** Added `get_emojis_for_tracks_batch()` function that fetches all emojis in single query with `WHERE track_id IN (...)`.

**Files Changed:**
- `03-backend-radio-api-extension.md` - Added batch fetching helper and usage example

**Impact:** Prevents severe performance degradation on playlist/search endpoints.

---

### 2. FTS5 Index Population Verification (CRITICAL)
**Problem:** No verification that FTS triggers properly populate search index after seeding.

**Solution:** Added verification query after seeding: check FTS count equals 50, log rebuild command if mismatch.

**Files Changed:**
- `01-database-schema-migration.md` - Added verification step in `seed_initial_emojis()`

**Impact:** Ensures search functionality works after migration.

---

### 3. Transaction Isolation for Race Conditions (CRITICAL)
**Problem:** Default DEFERRED transactions don't prevent race conditions in concurrent emoji additions.

**Solution:** Changed to `BEGIN IMMEDIATE` transactions for atomic write lock.

**Files Changed:**
- `02-backend-emoji-router.md` - Updated `add_emoji_to_track_mutation()` to use `BEGIN IMMEDIATE`

**Impact:** Accurate use_count under concurrent load, no lost updates.

---

## High Priority Changes

### 4. Unbounded Memory Growth in EmojiPicker (HIGH)
**Problem:** Loading all 3,600+ emojis into React state causes lag on slower devices.

**Solution:** Implemented react-query `useInfiniteQuery` with pagination (100 emojis per page, "Load More" button).

**Files Changed:**
- `06-frontend-emoji-picker-component.md` - Replaced full load with infinite scroll
- `04-frontend-setup-toast-and-shared-state.md` - Added pagination params to `getAllEmojis()`

**Impact:** Reduced initial DOM nodes from 4,100 to ~100, smooth performance.

---

### 5. Missing Pagination on Backend (HIGH)
**Problem:** `/api/emojis/all` endpoint returns unbounded results.

**Solution:** Added `limit` and `offset` query parameters (default: limit=100).

**Files Changed:**
- `02-backend-emoji-router.md` - Updated `get_all_emojis()` endpoint and query function

**Impact:** Prevents memory issues and slow responses on Pi deployment.

---

### 6. No Keyboard Navigation (HIGH - Accessibility)
**Problem:** Emoji picker click-only, violating WCAG 2.1 guidelines.

**Solution:** Added full keyboard support: arrow keys, Enter/Space to select, Escape to close, visual focus indicator.

**Files Changed:**
- `06-frontend-emoji-picker-component.md` - Added keyboard event handlers and focus state

**Impact:** Accessible to keyboard-only users, better power user UX.

---

### 7. Incomplete ComparisonView Integration (HIGH)
**Problem:** Plan showed stubbed code `// Update track_a in store` without implementation.

**Solution:** Added `updateTrackInPair()` method to comparisonStore, explicit implementation.

**Files Changed:**
- `08-integrate-emojis-everywhere.md` - Added store method and usage instructions

**Impact:** Clear implementation path, no runtime failures.

---

### 8. Custom Emoji Upload Blocking (HIGH)
**Problem:** Processing 5MB GIF blocks FastAPI worker thread for 5-10 seconds.

**Solution:** **Complete redesign** - CLI script instead of web upload. Offline processing, no blocking.

**Files Changed:**
- Created `10-custom-emoji-cli-script.md` (replaced `10-custom-emoji-upload.md`)
- Added `scripts/add-custom-emoji.py` specification
- Added `scripts/bulk-tag-emoji.py` specification
- Reduced file size limit to 1MB, frame limit to 20 (prevents even CLI blocking)

**Impact:** Zero server blocking, simpler implementation, perfect for personal project.

---

### 9. No Emoji Categories (HIGH - Deferred)
**Problem:** 3,600+ emojis hard to browse without categories.

**Solution:** **Skipped for MVP** - rely on search + top-50. Can add later if needed.

**Impact:** Simpler initial implementation, validate demand first.

---

## Medium Priority Changes

### 10. Confusing use_count Semantics (MEDIUM)
**Problem:** "Most Used" label misleading (shows lifetime additions, not current usage).

**Solution:** Renamed to "Most Added" in picker UI.

**Files Changed:**
- `06-frontend-emoji-picker-component.md` - Changed label from "Most Used" to "Most Added"

**Impact:** Clearer user understanding, no confusion.

---

### 11. Dual-Identifier Column Naming (MEDIUM)
**Problem:** Column named `emoji_unicode` holds both Unicode chars and "custom:uuid" strings.

**Solution:** Renamed column to `emoji_id` throughout schema and code.

**Files Changed:**
- `01-database-schema-migration.md` - All table definitions and triggers
- `02-backend-emoji-router.md` - All Pydantic models, functions, endpoints
- `03-backend-radio-api-extension.md` - Batch fetching functions
- `04-frontend-setup-toast-and-shared-state.md` - TypeScript interfaces and API functions
- `10-custom-emoji-cli-script.md` - CLI scripts and database queries

**Impact:** Clearer schema, accurate naming, no confusion.

---

### 12. No Bulk Operations (MEDIUM)
**Problem:** Tagging 100 tracks one-by-one is tedious.

**Solution:** Added CLI script for bulk tagging (`scripts/bulk-tag-emoji.py`).

**Files Changed:**
- `10-custom-emoji-cli-script.md` - Full bulk tagging script specification

**Impact:** Efficient playlist/pattern-based tagging workflows.

---

### 13. Compact Mode Can't Add Emojis (MEDIUM)
**Problem:** Tables/mini-display compact mode removes "+ Add" button.

**Solution:** **Accepted as-is** - compact mode is remove-only. Add emojis in detail views (RadioPlayer/ComparisonView).

**Impact:** Maintains truly compact display, clear mode distinction.

---

### 14. Optimistic Update Duplicates (MEDIUM)
**Problem:** Spam clicking "+ Add" causes duplicate emojis in UI before API rejection.

**Solution:** Added `isAdding`/`isRemoving` states to hook, disable buttons during requests.

**Files Changed:**
- `04-frontend-setup-toast-and-shared-state.md` - Added state tracking to `useTrackEmojis` hook
- `05-frontend-emoji-reactions-component.md` - Added props for disable states, conditional button styles
- `08-integrate-emojis-everywhere.md` - Updated `EmojiTrackActions` to pass disable states

**Impact:** No visual glitches, clear feedback during API calls.

---

### 15. No Custom Emoji Storage Limits (MEDIUM)
**Problem:** Unlimited custom emoji uploads could fill disk.

**Solution:** **No limits** - personal single-user project, document in script help.

**Impact:** User freedom, simpler implementation, trust-based.

---

## Architectural Changes Summary

### Database Schema
- **Column rename:** `emoji_unicode` → `emoji_id` (clearer for dual-identifier scheme)
- **FTS verification:** Added count check after seeding
- **Transaction isolation:** `BEGIN` → `BEGIN IMMEDIATE` for atomicity

### Backend API
- **Batch fetching:** `get_emojis_for_tracks_batch()` to prevent N+1 queries
- **Pagination:** `limit`/`offset` params on `/api/emojis/all`
- **Search limit:** Added `LIMIT 100` to FTS queries
- **Custom upload removed:** No web endpoint, CLI script only

### Frontend
- **Infinite scroll:** react-query `useInfiniteQuery` for emoji pagination
- **Keyboard navigation:** Full arrow key + Enter/Space support
- **Button disable:** `isAdding`/`isRemoving` states prevent spam clicks
- **Store method:** `updateTrackInPair()` for ComparisonView integration
- **Label change:** "Most Used" → "Most Added"

### CLI Scripts (New)
- **add-custom-emoji.py:** Offline custom emoji processing and database insertion
- **bulk-tag-emoji.py:** Batch tagging by playlist/pattern/track IDs

---

## Files Created
1. `10-custom-emoji-cli-script.md` (replaced `10-custom-emoji-upload.md`)
2. `PLAN-REVIEW-CHANGES.md` (this file)

## Files Modified
1. `README.md` - Updated task descriptions and dependencies
2. `01-database-schema-migration.md` - Column rename, FTS verification, normalize function update
3. `02-backend-emoji-router.md` - IMMEDIATE transactions, pagination, column rename
4. `03-backend-radio-api-extension.md` - Batch fetching helper
5. `04-frontend-setup-toast-and-shared-state.md` - Pagination, disable states, column rename
6. `05-frontend-emoji-reactions-component.md` - Disable state props and UI
7. `06-frontend-emoji-picker-component.md` - Infinite scroll, keyboard nav, label change, column rename
8. `08-integrate-emojis-everywhere.md` - Store method, disable states propagation

## Implementation Priority

**Must fix before shipping:**
1. N+1 query batch fetching
2. FTS verification
3. IMMEDIATE transactions
4. Column rename to emoji_id

**High value, should include:**
5. Pagination (backend + frontend)
6. Keyboard navigation
7. ComparisonView store method
8. CLI scripts (custom emoji + bulk tag)

**Nice to have:**
9. Button disable states
10. Label rename "Most Added"

---

## Testing Checklist

### Database
- [ ] Migration to v31 creates all tables/indexes/triggers
- [ ] FTS verification logs success message (count = 50)
- [ ] Column rename applied throughout schema

### Backend
- [ ] Batch fetching returns correct emoji map for multiple tracks
- [ ] IMMEDIATE transactions prevent race conditions under concurrent load
- [ ] Pagination returns correct pages with limit/offset
- [ ] Search results limited to 100

### Frontend
- [ ] Infinite scroll loads more emojis on "Load More" click
- [ ] Keyboard navigation works (arrows, Enter, Escape)
- [ ] Buttons disable during API calls
- [ ] Picker shows "Most Added" label

### CLI Scripts
- [ ] add-custom-emoji.py successfully adds custom emoji
- [ ] bulk-tag-emoji.py tags entire playlist correctly
- [ ] File size and frame limits enforced

### Integration
- [ ] ComparisonView updateTrackInPair method updates correct track
- [ ] Custom emojis render as images, Unicode as text
- [ ] No N+1 queries in playlist endpoints

---

## Lessons Learned

1. **Always verify indexes:** FTS triggers can fail silently, verification catches it
2. **Pagination by default:** Unbounded queries bite you at scale
3. **Transaction isolation matters:** SQLite defaults are insufficient for concurrent writes
4. **CLI > Web for batch:** Personal projects benefit from simple scripts over complex UIs
5. **Keyboard accessibility:** Not optional, should be in initial plan
6. **Button states prevent bugs:** Disable during async prevents duplicate actions
7. **Column naming matters:** Misleading names cause long-term confusion

---

## Next Steps

1. Implement changes in order (database → backend → frontend → CLI)
2. Test each layer before moving to next
3. Verify no N+1 queries with database profiling
4. Test keyboard navigation with actual keyboard-only usage
5. Validate CLI scripts work on both desktop and Pi
6. Document bulk tagging patterns for common use cases
