# Emoji Reaction System for Music Minion Web App

## Implementation Status

**Last Updated:** 2026-02-13

| Task | Status | Description |
|------|--------|-------------|
| 01 | ✅ Complete | Database schema migration v31 with emoji tables, FTS search, triggers |
| 02 | ✅ Complete | Backend emoji router with CRUD endpoints and atomic operations |
| 03 | ✅ Complete | Backend radio API extension with batch emoji fetching |
| 04 | ✅ Complete | Frontend setup with sonner toast and useTrackEmojis hook |
| 05 | ✅ Complete | EmojiReactions component (badge display with remove) |
| 06 | ✅ Complete | EmojiPicker component using emoji-mart library |
| 07 | ✅ Complete | Emoji settings page with custom name editing |
| 08 | ✅ Complete | Universal integration (RadioPlayer, mini-display) |
| 09 | ✅ Complete | End-to-end testing verification |
| 10 | ✅ Complete | Custom emoji CLI scripts (optional) |

### What's Working Now

- **Database:** Schema v31 with `track_emojis` and `emoji_metadata` tables, FTS5 search index
- **Backend API:** All emoji endpoints functional (`/api/emojis/*`), including custom emoji delete
- **Frontend:** Emoji picker, reactions, settings page all built with custom emoji support
- **Integration:** RadioPlayer shows emojis, mini-display in nav shows compact emojis
- **Custom Emojis:** CLI scripts for adding/bulk-tagging, image processing with Pillow, renders as images
- **Dependencies:** `emoji`, `sonner`, `@emoji-mart/react`, `@emoji-mart/data`, `pillow` installed

### Remaining Work

All tasks complete! The emoji system is fully implemented including:
- Custom emoji upload via CLI (`scripts/add-custom-emoji.py`)
- Bulk tagging via CLI (`scripts/bulk-tag-emoji.py`)
- Frontend display of custom emojis as images
- Delete functionality in settings page

### Quick Verification

```bash
# Check database schema
sqlite3 ~/.local/share/music-minion/music_minion.db "SELECT * FROM schema_version"
# Expected: 31

# Check emoji count
sqlite3 ~/.local/share/music-minion/music_minion.db "SELECT COUNT(*) FROM emoji_metadata"
# Expected: 50

# Test API (with server running)
curl http://localhost:8642/api/emojis/top?limit=3
```

---

## Overview

This implementation plan adds a comprehensive emoji reaction system to the Music Minion web app. Users can tag tracks with multiple emojis (🔥💪🎯), customize emoji names, and browse an adaptive top-50 emoji picker that learns from usage patterns.

The system features:
- **Multi-emoji tagging** - Tracks can have any number of emoji reactions
- **Unlimited emoji support** - 50 curated emojis to start, but you can add ANY Unicode emoji (3,600+ available)
- **Custom emoji upload** - Upload your own images/GIFs as custom emojis (auto-resized, preserved animation)
- **Full-text search** - Fast FTS5-powered search across all emoji names (custom and default)
- **Adaptive picker** - Top 50 section learns from your usage and bubbles most-used emojis to the top
- **Recent emojis** - Last 10 used emojis appear at top of picker for quick access
- **Keyboard shortcut** - Ctrl/Cmd+E opens emoji picker from anywhere
- **Visual indicators** - Count badges show usage, inline display shows emojis in track lists
- **Custom naming** - Rename emojis to match your personal taxonomy (e.g., 🔥 = "banger")
- **Universal integration** - Works everywhere tracks appear (RadioPlayer, ComparisonView, mini-display, tables)

Future capability: Use emojis as dynamic playlist filters ("show all tracks with 🔥").

## Task Sequence

1. [01-database-schema-migration.md](./01-database-schema-migration.md) - Create database tables, seed initial 50 emojis, **column renamed to emoji_id**, FTS verification
2. [02-backend-emoji-router.md](./02-backend-emoji-router.md) - Emoji CRUD API with **IMMEDIATE transactions**, **pagination**, batch fetching
3. [03-backend-radio-api-extension.md](./03-backend-radio-api-extension.md) - Extend radio API with **batch emoji fetching** (N+1 query fix)
4. [04-frontend-setup-toast-and-shared-state.md](./04-frontend-setup-toast-and-shared-state.md) - Toast notifications, shared hook with **button disable states**
5. [05-frontend-emoji-reactions-component.md](./05-frontend-emoji-reactions-component.md) - Emoji badge display with **disable states**
6. [06-frontend-emoji-picker-component.md](./06-frontend-emoji-picker-component.md) - Picker modal using **emoji-mart** library (3600+ emojis, custom emoji support, built-in search/keyboard nav)
7. [07-frontend-emoji-settings-page.md](./07-frontend-emoji-settings-page.md) - Settings page for customizing emoji names
8. [08-integrate-emojis-everywhere.md](./08-integrate-emojis-everywhere.md) - **Universal integration** with updateTrackInPair store method
9. [09-end-to-end-testing.md](./09-end-to-end-testing.md) - Comprehensive testing
10. [10-custom-emoji-cli-script.md](./10-custom-emoji-cli-script.md) - **CLI scripts** for custom emoji upload and bulk tagging (no web upload)

## Success Criteria

**Database:**
- Schema version is 31
- Two new tables: `track_emojis` (associations) and `emoji_metadata` (names, usage stats, custom emoji support)
- Columns include `type` ('unicode'|'custom') and `file_path` for custom emoji images
- 50 curated music emojis seeded on migration
- Proper indexes for fast queries
- Custom emojis directory created at `~/.local/share/music-minion/custom_emojis/`

**Backend API:**
- All 7 emoji endpoints functional
- Top 50 query returns emojis ordered by use_count
- Search works on both custom and default names
- Adding emoji auto-creates metadata if missing
- use_count only increments on NEW associations (no double-counting)

**Frontend UI:**
- Emoji badges appear below track info on RadioPlayer
- "+ Add" button opens full picker modal
- Picker shows adaptive top 50 + searchable full grid
- Clicking badge removes emoji (toggle behavior)
- Settings page allows renaming any emoji
- Custom names persist and appear in search
- Navigation includes "Emojis" link

**Integration:**
- Emojis save immediately on add/remove
- Optimistic UI updates (no waiting for API)
- Emojis persist across track changes
- No duplicate emojis on single track
- Search finds emojis by custom or default names
- Most-used emojis bubble to top of picker over time

## Execution Instructions

1. **Execute tasks in numerical order (01 → 08)**
   - Each task file contains:
     - Files to modify/create
     - Implementation details with code snippets
     - Acceptance criteria for verification
     - Dependencies on previous tasks

2. **Verification at each phase:**
   - **After Task 01:** Run app, check migration logs and database
   - **After Task 02-03:** Test backend API endpoints with curl
   - **After Task 04-07:** Test frontend UI in browser
   - **Task 08:** Comprehensive end-to-end testing

3. **Testing strategy:**
   - Unit test: Each component/function in isolation
   - Integration test: API → UI flow works
   - E2E test: Full user journey (add emoji → customize name → search → use)

## Dependencies

**External:**
- SQLite 3.x (already in use)
- FastAPI (already in use)
- React + TypeScript (already in use)
- TanStack Router (already in use)
- TanStack Query / react-query (already in use)
- **NEW:** `emoji` Python package for emoji name lookups (`uv add emoji`)
- **NEW:** `Pillow` Python imaging library for custom emoji processing (`uv add pillow`)
- **NEW:** `sonner` React toast library for error notifications (`npm install sonner`)
- **NEW:** `emoji-mart` React emoji picker with custom emoji support (`npm install @emoji-mart/react @emoji-mart/data`)

**Internal:**
- Requires Music Minion v30 schema (existing)
- Uses existing database connection patterns
- Integrates with existing RadioPlayer component
- Follows functional programming style (pure functions, immutable state)

**Development:**
- Run: `uv run music-minion --web` (starts backend + frontend)
- Database path: `~/.local/share/music-minion/music_minion.db`
- Backend: http://localhost:8642
- Frontend: http://localhost:5173

**Pi Deployment:**
⚠️ **IMPORTANT: Follow this exact deployment sequence to avoid downtime**

1. **Stop Pi server first:**
   ```bash
   ssh piserver 'cd ~/music-minion/docker/pi-deployment && docker compose down'
   ```

2. **Deploy code to Pi:**
   ```bash
   ./scripts/deploy-to-pi.sh
   ```

3. **Migrate desktop database:**
   ```bash
   uv run music-minion --dev  # Will auto-migrate to v31
   # Verify: sqlite3 ~/.local/share/music-minion/music_minion.db "SELECT * FROM schema_version"
   ```

4. **Wait for Syncthing to sync database:**
   - Check Syncthing UI to ensure `~/.local/share/music-minion/` folder is synced
   - Verify timestamp on Pi matches desktop

5. **Start Pi server:**
   ```bash
   ssh piserver 'cd ~/music-minion/docker/pi-deployment && docker compose up -d'
   ```

6. **Verify deployment:**
   ```bash
   # Check Pi has v31 schema
   ssh piserver "sqlite3 ~/.local/share/music-minion/music_minion.db 'SELECT * FROM schema_version'"
   ```

**Why this order matters:** If Pi runs old code against v31 database, it will crash. Desktop must migrate first, then sync, then Pi starts with new code.

## Architecture Notes

**use_count Semantics:**
- Represents "lifetime popularity" - how many times you've ADDED this emoji across all tracks
- Only increments when creating NEW track-emoji association
- Does NOT decrement on removal (preserves usage history)
- Powers adaptive top 50 sorting

**Data Flow:**
1. User clicks "+ Add" in RadioPlayer
2. EmojiPicker fetches top 50 + all emojis from API
3. User selects emoji
4. POST to `/api/emojis/tracks/{id}/emojis`
5. Backend: Insert track_emoji row, increment use_count
6. Frontend: Optimistic update shows badge immediately
7. Badge click → DELETE → Badge disappears

**Search Implementation (FTS5):**
- Uses SQLite FTS5 virtual table for fast full-text search
- Searches both custom_name and default_name simultaneously
- Supports prefix matching (`fire*`), phrases (`"red heart"`), boolean operators (`fire OR energy`)
- Automatically stays in sync via triggers (insert/update/delete on emoji_metadata)
- Scales to thousands of emojis without performance degradation
- Frontend debounces search input (300ms)
- Empty search shows all emojis

**Top 50 Calculation:**
- SQL: `ORDER BY use_count DESC, last_used DESC LIMIT 50`
- No caching needed (query is fast with index)
- Recomputed on every picker open (ensures fresh data)
- Initially shows 50 curated emojis (all have use_count=0)
- Over time, becomes personalized as you use emojis
