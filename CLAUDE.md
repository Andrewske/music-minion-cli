# CLAUDE.md

Music Minion CLI: Contextual music curation with multi-source support (local, SoundCloud, Spotify)

## Project Context

**Personal Project - Single User**:
- This is a personal tool for one user (me)
- May share with others later, but not currently
- **No production-ready requirements**: Breaking changes are fine
- **No backwards compatibility needed**: Delete old code, refactor aggressively
- **No phased rollouts**: Ship changes immediately
- **Fast iteration over stability**: Move quickly, fix issues as they arise

**What This Means**:
- ✅ Aggressive refactoring without deprecation warnings
- ✅ Breaking database schema changes (can manually migrate)
- ✅ Remove unused code immediately (no "just in case")
- ✅ Experimental features can go straight to main
- ✅ Skip migration paths - direct upgrades only
- ❌ No feature flags for gradual rollout
- ❌ No backwards compatibility shims
- ❌ No multi-version support

## Architecture

**Functional over Classes (CRITICAL)**:
- ALWAYS question if a class is necessary - prefer functions with explicit state passing
- Only use classes for: NamedTuple, dataclass, or framework requirements with explicit justification
- Pass state explicitly via `AppContext` dataclass, never global variables
- Pure functions: take context, return new context - no mutations
- Command handlers: `(AppContext, str, list) -> (AppContext, bool)`

**blessed UI Three-Tier Rendering**:
- Full redraw: Track change, terminal resize, initial render
- Input redraw: Typing, command palette filtering
- Partial redraw: Clock/progress bar only (flicker elimination)
- Immutable state: All updates via `dataclasses.replace()`, never mutation
- Pure render functions: `(terminal, state, position) -> height_used`
- **Always use `write_at()` for positioned output** (clears line by default, prevents text overlap)

**Multi-Source Provider Architecture**:
- Provider protocol: Pure functions (`authenticate()`, `sync_library()`, `get_stream_url()`)
- Immutable `ProviderState` dataclass with builder methods
- No global variables or class instance state
- Background syncing: Thread-safe state updates via global sync state
- Track deduplication: TF-IDF cosine similarity matching

**UI Component Organization**:
- Keyboard handlers: `ui/blessed/events/keys/` (modular by mode: normal, wizard, comparison, playlist_builder, etc.)
- Components: `ui/blessed/components/` (pure render functions)
- Helpers: `ui/blessed/helpers/` (scrolling, terminal utilities, `write_at()`)
- State selectors: `ui/blessed/state_selectors.py` (memoized state derivations)
- Internal commands: `ui/blessed/events/commands/executor.py` (async command handlers)

**UI Mode System**:
- Mode detection via `detect_mode()` in `events/keyboard.py`
- Priority order: comparison > wizard > builder > track_viewer > analytics > editor > normal
- Each mode has: state fields in `UIState`, key handler, render component
- State mutations via `dataclasses.replace()` (immutable updates)

## Code Requirements

**Logging (CRITICAL)**:
```python
# Background operations - use loguru directly
from loguru import logger
logger.info("message")
logger.exception("error")  # In except blocks for stack traces

# User-facing - use unified log() helper (dual output: file + UI)
from music_minion.core.output import log
log("✅ Success", level="info")

# Background threads - suppress stdout
threading.current_thread().silent_logging = True
```

**NEVER use print()** - logs lost on restart, no rotation, breaks blessed UI

**Always use `uv run`** for Python script execution

**Type Safety**:
- Type hints required for parameters and returns
- No circular imports

**Imports**:
- Absolute imports preferred (`from music_minion.core import database`)
- Exception: `__init__.py` files and sibling modules within same package

**Functions**:
- ≤20 lines, ≤3 nesting levels
- Single responsibility

## Critical Patterns

**Data Loss Prevention**:
- Track data ownership: `source='user'|'ai'|'file'|'soundcloud'|'spotify'`
- NEVER remove data without checking ownership
- Only remove data you own (e.g., only remove `source='file'` tags during import)

**Atomic File Operations (Mutagen)**:
```python
temp_path = file_path + '.tmp'
try:
    shutil.copy2(file_path, temp_path)
    audio = MutagenFile(temp_path)
    # ... modify ...
    audio.save()
    os.replace(temp_path, file_path)  # Atomic
except Exception:
    if os.path.exists(temp_path): os.remove(temp_path)
    raise
```

**Database**:
- Batch updates: `executemany()` (30% faster)
- Single transaction: Commit once after all updates
- Always: `with get_db_connection() as conn:`

**Error Handling**:
- Use `logger.exception()` in except blocks (auto stack traces)
- NEVER bare except - catch specific exceptions
- Include context: file, provider, playlist name
- Background threads: Must wrap in try/except (exceptions don't propagate)

**Progress Reporting**:
- Scale with data: `max(1, total // 100)` for 1% intervals
- Use callbacks for thread-safe UI updates

**Change Detection**:
- mtime: Float timestamps for sub-second precision
- Get mtime AFTER write to capture own changes

## Development

**Commands**:
- Primary: `music-minion`
- Dev mode: `music-minion --dev` (hot-reload)
- IPC: `music-minion-cli play|skip|love|...`
- Locate opus: `music-minion locate-opus /path/to/folder [--apply]`
- Web UI backend: `uv run uvicorn web.backend.main:app --reload`
- Web UI frontend: `cd web/frontend && npm install && npm run dev`

**Development Workflow**:
- Environment setup: `uv sync --dev`, then `uv pip install -e .`
- Run with hot-reload: `uv run music-minion --dev`
- Test suite: `uv run pytest` (all) or `uv run pytest path/to/test.py::test_case` (single)
- Code quality: `uv run ruff check src` and `uv run ruff format src`

**Testing Procedures**:
- Autoplay: Test shuffle mode, sequential mode with playlists, edge cases
- Edge cases: No available tracks, single track playlists, MPV crashes
- Performance validation: No UI flicker, < 0.5s gap between tracks

**Key Dependencies**:
- mutagen (MP3/M4A/Opus metadata)
- blessed (terminal UI)
- loguru (centralized logging)
- spotipy (Spotify API)
- fastapi (web API backend)
- uvicorn (ASGI server)
- pydub (audio waveform generation)
- react + typescript (web UI frontend)
- wavesurfer.js (waveform visualization)
- zustand (React state management)
- @tanstack/react-query (API data fetching)

**Database**: SQLite schema v22 in `core/database.py`
- Migrations: Idempotent with try/except for duplicate columns
- Key tables: `tracks`, `playlists`, `playlist_tracks`, `playlist_builder_state`

## Web UI Architecture

**Backend (FastAPI)**:
- RESTful API at `/api/*` endpoints
- Dependency injection for database connections (`web/backend/deps.py`)
- Pydantic schemas for request/response validation (`web/backend/schemas.py`)
- Routers: `comparisons.py` (ELO sessions), `tracks.py` (audio streaming)
- Waveform generation: pydub for audio analysis, cached as JSON peaks
- Audio streaming: direct file serving with proper Content-Type headers
- Testing: pytest with test coverage for schemas and endpoints

**Frontend (React + TypeScript)**:
- Vite build system with hot module replacement
- Component architecture:
  - `ComparisonView.tsx` - Main comparison interface
  - `TrackCard.tsx` - Track metadata display
  - `WaveformPlayer.tsx` - Audio visualization with wavesurfer.js
  - `SwipeableTrack.tsx` - Touch gesture wrapper
  - `SessionProgress.tsx` - Progress indicator
  - `ErrorState.tsx` / `SessionComplete.tsx` - State screens
- Hooks:
  - `useComparison.ts` - Comparison session logic
  - `useWavesurfer.ts` - Waveform initialization and control
  - `useAudioPlayer.ts` - Audio playback state
  - `useSwipeGesture.ts` - Touch gesture detection (@use-gesture/react)
- State: Zustand store for session and track state
- API Layer: Centralized fetch wrapper with error handling
- Styling: Tailwind CSS with custom utility classes

## Documentation References

- `ai-learnings.md` - Patterns, best practices, gotchas
- `docs/playlist-system-plan.md` - Implementation history
- `docs/incomplete-items.md` - Future roadmap
- `docs/opencode-mobile-web-ui-plan.md` - Web UI implementation details

**Future Roadmap - Major Features**:
- Metadata enhancement system (conversational AI-driven cleanup)
  - Pattern-based cleanup (promotional text removal, artist consolidation)
  - AI prompt optimization that learns from user feedback
  - External enrichment (SoundCloud integration, scraping framework)
- Expanded web UI features (playlist management, track search)
- Global hotkey support (daemon mode)
- YouTube Music / Apple Music integration

## Recent Features

**Mobile Web UI** (v23 - 2025-12-08):
- Progressive web app for mobile ELO comparisons
- Real-time waveform visualization with wavesurfer.js
- Touch-optimized swipe gestures (left/right to choose winner)
- Quick seek bar for audio preview (tap anywhere to jump)
- Session progress tracking with remaining comparisons count
- Responsive design with Tailwind CSS
- Tech stack: FastAPI backend, React + TypeScript frontend, Zustand state management
- Key endpoints:
  - `POST /api/comparisons/session` - Start new comparison session
  - `GET /api/comparisons/next-pair` - Fetch next track pair
  - `POST /api/comparisons/record` - Record comparison result
  - `GET /api/tracks/{id}/stream` - Stream audio file
  - `GET /api/tracks/{id}/waveform` - Get waveform visualization data
  - `POST /api/tracks/{id}/archive` - Archive track
- Files: `web/backend/`, `web/frontend/src/`

**Filter Editor UX Improvements** (v22+):
- List-based selection for field/operator/value (no more manual typing)
- Auto-save on Escape in filter editor
- Shared filter input helper between playlist builder and wizard
- Better state tracking for add vs edit operations
- Files: `ui/blessed/helpers/filter_input.py`, `ui/blessed/state.py`

**Metadata Sync (v22+)**:
- `write_metadata_to_file()` - writes title, artist, album, genre, year, bpm, key to files
- `update_track_metadata()` - now writes to both database AND file
- `sync` command exports DB metadata to files (DB is source of truth)
- Supports MP3 (ID3), M4A (MP4), Opus (Vorbis comments)

**Opus Migration** (v22+):
- `locate-opus` CLI command for MP3→Opus migration
- Tiered matching: filename exact → title exact → fuzzy (85% TF-IDF)
- Preserves all history (ratings, ELO, playlists) via track_id
- Workflow: download opus alongside mp3 → locate-opus --apply → sync → delete mp3

**Playlist Builder** (v22):
- Bulk track selection for playlist building
- Entry: Press `b` from track viewer on manual playlist
- Sort by: title, artist, year, album, genre, bpm
- Filter with text/numeric operators (contains, equals, >, <, etc.)
- State persistence: scroll position, sort, filters saved per playlist
- Files: `components/playlist_builder.py`, `events/keys/playlist_builder.py`

**ELO Rating System**:
- Track comparison mode for rating tracks
- Rating history viewer
- Comparison history viewer

---

**Last Updated**: 2025-12-08
