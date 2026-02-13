# Web Playlist Builder Implementation

## Overview

Build a dedicated web-based "audition mode" for curating manual playlists in Music Minion. Users set filters to define candidate tracks, play them on loop, and use keyboard shortcuts (`web-winner`/`web-archive`) to quickly add or skip tracks. Skipped tracks and builder filters are persisted per-playlist, enabling resumable curation sessions.

**Key Features:**
- Filter-based candidate selection (genre, BPM, year, key)
- Loop playback until decision made
- Keyboard shortcuts for rapid curation
- Persistent skip list (never show again per playlist)
- Session state survives browser restarts
- Manual playlists only (smart playlists excluded)

## Task Sequence

1. [01-database-migration.md](./01-database-migration.md) - Add v27 schema with 3 new tables
2. [02-domain-logic-builder.md](./02-domain-logic-builder.md) - Core business logic (pure functions)
3. [03-backend-api-routes.md](./03-backend-api-routes.md) - FastAPI REST endpoints
4. [04-cli-ipc-integration.md](./04-cli-ipc-integration.md) - Context-aware command routing
5. [05-frontend-api-client.md](./05-frontend-api-client.md) - TypeScript API client
6. [06-frontend-state-management.md](./06-frontend-state-management.md) - React Query hook
7. [07-frontend-playlist-builder-page.md](./07-frontend-playlist-builder-page.md) - Full UI implementation

## Success Criteria

### Backend (Python)
- ✅ Database migrates to v27 without errors
- ✅ Domain functions handle filters, candidates, skip/add operations
- ✅ API endpoints validate manual playlists and return proper errors
- ✅ CLI commands route correctly based on `active_web_mode`
- ✅ WebSocket broadcasts builder messages

### Frontend (TypeScript)
- ✅ API client successfully communicates with backend
- ✅ React Query hook manages session state with optimistic updates
- ✅ Page loads, plays audio on loop, and advances on decision
- ✅ Keyboard shortcuts trigger add/skip via WebSocket
- ✅ Filter updates re-fetch candidate pool
- ✅ "No candidates" state displayed when pool exhausted

### Integration
- ✅ Start session → Get first candidate → Audio plays
- ✅ Click "Add" → Track added to playlist → Next candidate loads
- ✅ Click "Skip" → Track added to skip list → Next candidate loads
- ✅ Press `web-winner` keyboard shortcut → Same as "Add" button
- ✅ Press `web-archive` keyboard shortcut → Same as "Skip" button
- ✅ Close browser and reopen → Session resumes from last track
- ✅ Set filters (genre, BPM) → Candidate pool respects filters
- ✅ Unskip track → Track reappears in candidates

## Execution Instructions

1. **Execute tasks in numerical order** (01 → 07)
2. Each task file contains:
   - Files to modify/create
   - Implementation details with code samples
   - Acceptance criteria
   - Dependencies (must complete prior tasks first)
   - Verification steps
3. **Test after each task** before moving to next
4. Run full integration test after task 07

### Commands

```bash
# Start development environment (all services)
uv run music-minion --web

# Run backend tests
uv run pytest tests/test_builder.py
uv run pytest web/backend/tests/test_builder_routes.py

# Frontend development
cd web/frontend
npm run dev

# Database inspection
sqlite3 ~/.local/share/music-minion/music_minion.db
```

## Dependencies

### External
- Python 3.11+ with `uv` package manager
- SQLite (bundled with Python)
- Node.js 18+ and npm
- FastAPI backend running on port 8642
- Vite frontend running on port 5173

### Internal
- Existing `domain/playlists/filters.py` for filter logic
- Existing `domain/playlists/crud.py` for playlist operations
- Existing IPC server with WebSocket support
- Existing blessed UI command executor

## Architecture Patterns

**Backend (Functional Python):**
- Pure functions with explicit state passing
- No classes (except dataclasses for context)
- Parameterized SQL queries (prevent injection)
- Batch operations where possible
- Type hints on all functions

**Frontend (React + TypeScript):**
- React Query for server state management
- Optimistic updates for UX responsiveness
- WebSocket for real-time CLI integration
- TypeScript strict mode enabled

**Database:**
- SQLite with WAL mode for concurrency
- Foreign keys with CASCADE delete
- Indexes on frequently queried columns
- Migration-based schema evolution

## File Manifest

**Backend (Python):**
1. `src/music_minion/core/database.py` - v27 migration (~20 lines)
2. `src/music_minion/domain/playlists/builder.py` - NEW (~200 lines)
3. `web/backend/routers/builder.py` - NEW (~150 lines)
4. `web/backend/schemas.py` - Add Pydantic models (~40 lines)
5. `web/backend/main.py` - Register router (~2 lines)
6. `src/music_minion/context.py` - Add fields + helper (~15 lines)
7. `src/music_minion/ui/blessed/events/commands/executor.py` - Update handlers (~30 lines)
8. `src/music_minion/ipc/server.py` - Message format docs (~5 lines)

**Frontend (TypeScript):**
1. `web/frontend/src/api/builder.ts` - NEW (~80 lines)
2. `web/frontend/src/hooks/useBuilderSession.ts` - NEW (~60 lines)
3. `web/frontend/src/pages/PlaylistBuilder.tsx` - NEW (~200 lines)
4. `web/frontend/src/hooks/useIPCWebSocket.ts` - Add handlers (~15 lines)
5. `web/frontend/src/App.tsx` - Add route (~2 lines)

**Tests:**
1. `tests/test_builder.py` - NEW (domain logic tests)
2. `web/backend/tests/test_builder_routes.py` - NEW (API tests)

**Total: ~780 lines across 12 files + 2 test files**

## Known Limitations

1. **Performance:** Candidate query limited to 100 tracks (uses NOT EXISTS optimization)
2. **Audio Formats:** Requires browser-compatible formats (MP3, OGG, OPUS)
3. **WebSocket:** Single connection per tab (no multi-tab sync)
4. **Filter Complexity:** Reuses smart playlist filter logic (limited operators)
5. **No Unskip UI in MVP:** Users cannot review/unskip tracks in initial release. Backend endpoints exist (`GET /skipped`, `DELETE /skipped/{track_id}`). UI will be added based on user feedback.

## Error Handling Pattern

**Domain Layer:** Raises exceptions for error conditions (ValueError for invalid inputs, sqlite3.Error for DB issues)

**API Layer:** Catches exceptions and converts to HTTPException with appropriate status codes

**Frontend:** React Query catches errors and displays toast notifications

## Future Enhancements

- **Skipped tracks review UI:** Component to view and unskip accidentally skipped tracks
- Waveform visualization for track preview
- Batch operations (add/skip multiple tracks)
- Collaborative building (multi-user sessions)
- Undo/redo functionality
- AI-assisted filter suggestions

## Troubleshooting

**Database migration fails:**
```bash
# Check current schema version
sqlite3 ~/.local/share/music-minion/music_minion.db "SELECT * FROM schema_version"

# Backup database
cp ~/.local/share/music-minion/music_minion.db ~/.local/share/music-minion/music_minion.db.backup
```

**Audio won't play:**
- Check browser console for errors
- Verify `/api/tracks/{id}/stream` endpoint works
- Check file format compatibility
- Verify CORS headers allow streaming

**WebSocket not connecting:**
- Check IPC server is running: `ps aux | grep music-minion`
- Verify port 8765 is open
- Check browser console for WebSocket errors
- Try `ws://localhost:8765` directly

**Keyboard shortcuts not working:**
- Verify CLI commands configured: `music-minion-cli web-winner`
- Check IPC socket exists: `ls -la $XDG_RUNTIME_DIR/music-minion/control.sock`
- Check WebSocket message flow in browser console
- Verify `active_web_mode` set correctly in context
