# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Music Minion CLI is a contextual music curation tool that learns user preferences over time. It focuses on capturing temporal patterns (when you like songs) rather than static ratings, building a "music minion" that understands your taste evolution.

## Architecture & Design Principles

### Core Architecture
- **Functional over Classes**: Use functions and modules, avoid complex class hierarchies. **CRITICAL**: Always question if a class is necessary - prefer functions with explicit state passing over classes with instance variables. Only use classes for simple data containers (NamedTuple, dataclass) or when there's compelling justification that must be explicitly provided and approved.
- **Explicit State Passing**: Use `AppContext` dataclass to pass state explicitly instead of global variables
- **Pure Functions**: Functions take context, return new context - no hidden mutations
- **Single Responsibility**: Each function ≤20 lines, ≤3 nesting levels
- **Fail Fast**: Critical errors (missing mpv, no music) should exit with clear messages
- **Graceful Degradation**: Non-critical errors (AI failures, corrupted files) should log and continue

### blessed UI Architecture Patterns
**Decision**: Migrated from Textual to blessed for full control and functional programming style

**Key Patterns**:
1. **Immutable State Updates**: All state changes via `dataclasses.replace()`, never mutation
2. **Pure Rendering Functions**: `(terminal, state, position) -> height_used`
3. **Partial Rendering**: Three-tier strategy eliminates flashing
   - Full redraw: Track change, terminal resize, initial render
   - Input redraw: Typing, command palette filtering
   - Partial redraw: Clock and progress bar only (every second during playback)
4. **Event Loop**: `poll input → update state → render → repeat`
5. **Layout Calculation**: Single function computes all Y positions from heights
6. **blessed Colors**: Function composition `term.bold_cyan("text")`

**Benefits**:
- ✅ Fully functional approach (no classes except data containers)
- ✅ Direct terminal control without framework overhead
- ✅ Smooth, flicker-free UI updates
- ✅ Professional appearance with precise positioning
- ✅ Easy to test (pure functions)

**Files**:
- `ui/blessed/state.py` - Immutable UIState dataclass
- `ui/blessed/app.py` - Main event loop with three-tier rendering
- `ui/blessed/components/dashboard.py` - Full and partial render functions
- `ui/blessed/events/keyboard.py` - Pure keyboard event handlers

### Project Structure
```
music-minion/
├── src/music_minion/
│   ├── __init__.py
│   ├── main.py                 # Entry point and interactive loop
│   ├── cli.py                  # CLI entry point
│   ├── context.py              # AppContext for functional state passing
│   ├── router.py               # Command routing
│   ├── helpers.py              # Context helpers and utilities
│   ├── command_palette.py      # Command palette widget
│   ├── dev_reload.py           # Hot-reload development mode
│   ├── ui.py                   # Legacy UI (deprecated)
│   │
│   ├── core/                   # Core infrastructure
│   │   ├── config.py           # Configuration loading (TOML)
│   │   ├── database.py         # SQLite operations (schema v9)
│   │   └── console.py          # Console utilities
│   │
│   ├── domain/                 # Business logic (functional)
│   │   ├── ai/                 # AI integration
│   │   │   ├── client.py       # OpenAI client
│   │   │   ├── prompt_manager.py    # Prompt versioning and learnings
│   │   │   ├── prompt_enhancement.py # AI prompt improvement
│   │   │   ├── review.py       # Conversational tag review
│   │   │   └── __init__.py
│   │   ├── library/            # Music library management
│   │   │   ├── models.py       # Track data models
│   │   │   ├── scanner.py      # Library scanning
│   │   │   ├── metadata.py     # Metadata extraction
│   │   │   ├── provider.py     # Provider protocol (abstract interface)
│   │   │   ├── deduplication.py # TF-IDF track matching across providers
│   │   │   ├── import_tracks.py # Batch provider track import
│   │   │   ├── providers/      # Provider implementations
│   │   │   │   ├── __init__.py # Provider registry
│   │   │   │   ├── local.py    # Local file provider
│   │   │   │   └── soundcloud/ # SoundCloud provider (OAuth + API)
│   │   │   │       ├── __init__.py  # Re-exports
│   │   │   │       ├── auth.py      # OAuth 2.0 + PKCE
│   │   │   │       └── api.py       # API operations
│   │   │   └── __init__.py
│   │   ├── playback/           # Audio playback
│   │   │   ├── player.py       # MPV integration
│   │   │   ├── state.py        # Playback state management
│   │   │   ├── resolver.py     # Multi-source stream URL resolution
│   │   │   └── __init__.py
│   │   ├── playlists/          # Playlist management
│   │   │   ├── crud.py         # Playlist CRUD operations
│   │   │   ├── filters.py      # Smart playlist filter logic
│   │   │   ├── ai_parser.py    # AI natural language parsing
│   │   │   ├── importers.py    # Import M3U/Serato playlists
│   │   │   ├── exporters.py    # Export to M3U8/Serato formats
│   │   │   └── __init__.py
│   │   └── sync/               # Bidirectional metadata sync
│   │       ├── engine.py       # Sync engine (local files)
│   │       ├── provider_metadata.py # Provider tag sync (database ↔ file metadata)
│   │       └── __init__.py
│   │
│   ├── commands/               # Command handlers
│   │   ├── admin.py            # Admin commands (quit, help)
│   │   ├── ai.py               # AI commands
│   │   ├── library.py          # Library management commands (multi-source)
│   │   ├── playback.py         # Playback commands
│   │   ├── playlist.py         # Playlist commands
│   │   ├── rating.py           # Rating commands
│   │   ├── sync.py             # Sync commands
│   │   ├── track.py            # Track commands
│   │   └── __init__.py
│   │
│   ├── ui/                     # User interface
│   │   ├── blessed/            # blessed-based interactive UI
│   │   │   ├── app.py          # Main blessed app loop
│   │   │   ├── state.py        # UI state (immutable)
│   │   │   ├── components/     # UI components
│   │   │   │   ├── dashboard.py
│   │   │   │   ├── history.py
│   │   │   │   ├── input.py
│   │   │   │   ├── palette.py
│   │   │   │   ├── layout.py
│   │   │   │   ├── wizard.py   # Smart playlist wizard
│   │   │   │   └── track_viewer.py # Track viewer component
│   │   │   ├── events/         # Event handlers
│   │   │   │   ├── keyboard.py
│   │   │   │   ├── review_handler.py # AI review event loop
│   │   │   │   └── commands/   # Modularized command handlers
│   │   │   │       ├── executor.py
│   │   │   │       ├── playlist_handlers.py
│   │   │   │       ├── track_viewer_handlers.py
│   │   │   │       └── wizard_handlers.py
│   │   │   └── styles/         # Styling and formatting
│   │   │       ├── palette.py
│   │   │       └── formatting.py
│   │   └── __init__.py
│   │
│   └── utils/                  # Utilities
│       ├── parsers.py          # Command parsing
│       ├── autocomplete.py     # Autocomplete logic
│       └── __init__.py
│
├── docs/
│   ├── playlist-system-plan.md # Implementation plan (Phases 1-7 complete)
│   └── incomplete-items.md     # Future enhancements and TODOs
├── ai-learnings.md             # Patterns and learnings for AI assistants
├── pyproject.toml
└── CLAUDE.md                   # This file
```

## Development Setup & Commands

### Environment Management
- Use **UV** for dependency and environment management
- Python 3.12+ required

### Key Dependencies
- **mutagen**: MP3/M4A metadata handling, ID3 tag operations
- **openai**: AI integration (optional) - natural language playlist parsing
- **blessed**: Terminal UI library for full-screen interactive dashboard
- **rich**: Terminal formatting, progress bars, and styling
- **prompt_toolkit**: Command palette with autocomplete and fuzzy search
- **pathlib**: Cross-platform path handling
- **tomllib**: TOML configuration loading (Python 3.11+)
- **pyserato**: Serato .crate file import/export for DJ integration
- **sqlite3**: Database operations (built-in)

### Entry Points
- Primary command: `music-minion`
- Interactive mode with commands: `play`, `love`, `skip`, `note "text"`
- Setup command: `music-minion init`
- Development mode: `music-minion --dev` (enables hot-reload)

### Development Mode
- **Hot-reload**: `music-minion --dev` enables automatic code reloading
- File changes are detected and modules reloaded instantly
- No need to restart the app during development
- State preserved (player, tracks, database connections)
- See `docs/hot-reload-usage.md` for detailed guide

## Key Technical Decisions

### UI Architecture (blessed)
- **blessed** for direct terminal control with functional programming style
- **Immutable State**: All UI state updates return new `UIState` instances (no mutation)
- **Pure Rendering**: Render functions take terminal, state, position - no side effects
- **Partial Rendering**: Only update changed regions (clock, progress bar) to eliminate flashing
- **Three-tier Update Strategy**:
  1. Full redraw on track change/terminal resize
  2. Input-only redraw on typing
  3. Partial redraw for time-sensitive elements (clock, progress)
- **Layout Calculation**: Single function computes all positions based on state
- **Event Loop**: Poll keyboard with timeout, update state, re-render
- **Benefits**: Full control, no framework overhead, functional patterns, professional UX

### AppContext Pattern
- **Explicit State Passing**: All application state in `AppContext` dataclass
- **No Global Variables**: Context passed explicitly to all functions
- **Immutable Updates**: Functions return new context instead of mutating
- **Command Handler Pattern**: `(AppContext, str, list) -> (AppContext, bool)`
- **Benefits**: Clear data flow, easier testing, no hidden mutations

### Multi-Source Provider Architecture
- **Provider Protocol**: Abstract interface in `domain/library/provider.py`
  - Pure functions: `authenticate()`, `sync_library()`, `get_stream_url()`
  - Immutable state: `ProviderState` dataclass with builder methods
  - Explicit state passing: No global variables or class instance state
- **Provider Registry**: `domain/library/providers/__init__.py`
  - Maps provider names to implementations
  - Currently: `local` (filesystem), `soundcloud` (OAuth + API)
  - Future: `spotify`, `youtube`
- **Track Deduplication**: TF-IDF text matching in `deduplication.py`
  - Fast batch matching (~10ms per track)
  - Cosine similarity with configurable threshold
  - Manual correction workflow via CSV export/import
- **Batch Import**: `import_tracks.py` with transaction safety
  - Whitelist validation for SQL injection protection
  - Atomic operations with explicit rollback
  - Progress reporting (1% intervals)
- **Provider Metadata Sync**: `sync/provider_metadata.py`
  - Bidirectional: database tags ↔ file metadata
  - Atomic file operations (copy-to-temp pattern)
  - Source tracking prevents data loss

### Audio Integration
- **MPV with JSON IPC** for cross-platform audio playback
- Handles complex audio processing while focusing on curation logic
- Socket-based communication for control from anywhere
- **Multi-source playback**: `playback/resolver.py` resolves stream URLs for providers

### Data Storage Strategy
- **SQLite**: Context data, ratings with timestamps, temporal patterns
- **File Metadata**: DJ-compatible ratings written to MP3/M4A comment fields
- Format: "085 - Great buildup, drops at 1:32"

### Configuration
- TOML files in `~/.config/music-minion/`
- Load with Python's built-in tomllib

### Logging Strategy
- **Two levels**: User-facing errors and detailed debug logs
- Preserve user workflow even when AI/metadata operations fail

## Core Features & Commands

### Interactive Rating System
- `archive` - Remove from rotation (never play again)
- `skip` - Skip without penalty (mood-dependent)
- `like` - Basic positive rating (auto-syncs to SoundCloud if track has soundcloud_id)
- `love` - Strong positive rating
- `unlike` - Remove SoundCloud like marker and unsync from SoundCloud
- `note "text"` - Add contextual notes

### AI Integration Commands
- `ai setup <key>` - Configure OpenAI API key
- `ai analyze library` - Batch process existing library
- `ai process batch` - Process accumulated unprocessed songs
- `ai review` - Conversational tag review with feedback and learning
- `ai enhance prompt` - AI-powered prompt improvement with testing
- `ai test` - Test current prompt on random tracks
- `ai usage` - View AI token usage and costs

### Playlist Commands (Phases 1-5 Complete)
- `playlist` - List all playlists with active indicator
- `playlist new manual <name>` - Create manual playlist
- `playlist new smart <name>` - Create smart playlist with interactive wizard
- `playlist new smart ai <name> "description"` - AI-parsed smart playlist
- `playlist delete <name>` - Delete playlist with confirmation
- `playlist rename <old> <new>` - Rename playlist
- `playlist show <name>` - Show playlist details and tracks
- `playlist active <name>` - Set active playlist (filters playback)
- `playlist active none` - Clear active playlist
- `playlist active` - Show current active playlist
- `playlist import <file>` - Import M3U/M3U8/Serato .crate
- `playlist export <name> [format]` - Export to m3u8, crate, or all
- `add <playlist_name>` - Add current track to playlist
- `remove <playlist_name>` - Remove current track from playlist

### Track Viewer
- Interactive track viewer for browsing playlist tracks
- Keyboard shortcuts: j/k (down/up), Enter (play), q (close)
- Shows track metadata: title, artist, album, BPM, key
- Accessible from playlist show command

### Track Search (New - 2025-11-16)
- `search` - Open interactive track search
- Real-time filtering across all tracks (title, artist, album, genre, tags, notes)
- Sequential 3-mode UI: Search → Detail → Action
- Quick action shortcuts: `p` (play), `a` (add to playlist), `e` (edit metadata)
- Keyboard navigation: ↑↓/j/k, Enter for details, Esc to close
- Performance: < 5ms filtering for 5000+ tracks (in-memory)

### Playback Commands (Phase 6 Complete)
- `shuffle` - Show current shuffle mode
- `shuffle on` - Enable shuffle mode (random playback)
- `shuffle off` - Enable sequential mode (playlist order)

### Sync Commands (Phase 7 Complete)
- `sync export` - Write all database tags to file metadata
- `sync import` - Import tags from changed files (incremental)
- `sync import --all` - Force full import from all files
- `sync status` - Show sync statistics and pending changes
- `sync rescan` - Rescan library for file changes (incremental)
- `sync rescan --full` - Full library rescan (all files)

### Library Commands (Multi-Source)
- `library active` - Show current active library
- `library active <provider>` - Switch active library (local, soundcloud, etc.)
- `library sync <provider>` - Sync tracks from provider (OAuth + API)
- `library auth <provider>` - Authenticate with provider (OAuth flow)
- `library match <provider>` - Match provider tracks to local library (deduplication)

### Context Tracking
- Store ratings with timestamp and context (time of day, day of week)
- Track preference patterns and evolution over time
- Mood correlation and session statistics
- Bidirectional sync with file metadata (Linux ↔ Windows/Serato)
- Multi-source integration (local files + SoundCloud/Spotify/YouTube)

## User Profile Context
- **Primary Library**: MP3 (4,766 files), M4A (368 files)
- **Location**: `~/Music`
- **Platform**: Linux (primary), expand to other platforms later

## Code Style Requirements
- Use type hints for function parameters and returns
- Prefer pathlib.Path over string paths
- Use context managers for file/database operations
- Keep business logic separate from UI code
- Write docstrings for public functions
- No circular imports
- Extract reusable code to `utils/` folder
- **Import Style**:
  - Use absolute imports (`from music_minion.core import database`)
  - Exception: Package-local imports in `__init__.py` files (e.g., `from .crud import create_playlist`)
  - Exception: Sibling module imports within same package (e.g., `from .models import Track` in `domain/library/`)
  - Rationale: Absolute imports are clearer, more refactor-safe, and easier for tools to resolve

## Critical Patterns & Best Practices

### Data Loss Prevention
**CRITICAL**: When implementing bidirectional sync or any data removal:
- Always track data ownership/source (`source='user'`, `source='ai'`, `source='file'`)
- NEVER remove data without checking ownership
- Only remove data you own (e.g., only remove `source='file'` tags during import)
- See `ai-learnings.md` section "Data Loss Prevention Through Ownership Tracking"

### Atomic File Operations
**CRITICAL**: All file writes must be atomic. Mutagen requires files to exist before saving, so copy first:
```python
import shutil

temp_path = file_path + '.tmp'
try:
    shutil.copy2(file_path, temp_path)  # Copy original to temp
    audio = MutagenFile(temp_path)      # Load temp file
    # ... modify audio tags ...
    audio.save()                         # Save in place (no filename)
    os.replace(temp_path, file_path)    # Atomic replace on Unix/Windows
except Exception:
    if os.path.exists(temp_path):
        os.remove(temp_path)
    raise
```

### Database Operations
- **Batch updates**: Use `executemany()` for bulk operations (30% faster)
- **Single transaction**: Commit once after all updates, not per-item
- **Context managers**: Always use `with get_db_connection() as conn:`
- **Migrations**: Idempotent with try/except for "duplicate column" errors

### Error Handling
- **NEVER use bare except**: Always catch specific exceptions
- **Informative errors**: Include file, operation, and cause in error messages
- **Silent failure**: Only for auto-operations (auto-export, auto-sync)
- **Background threads**: Must wrap in try/except (exceptions don't propagate)

### Change Detection
- **mtime tracking**: Use float timestamps for sub-second precision
- **Get mtime AFTER write**: Captures your own changes correctly
- **Race conditions**: Be aware of order of operations

### Progress Reporting
- **Scale with data**: Use `max(1, total // 100)` for 1% intervals
- **Not fixed counts**: Avoids "no feedback for first 100 items" problem

### Validation
- **Fail fast**: Validate at entry point, not during processing
- **File formats**: Check `isinstance(audio, (MP4, ID3))` before operations
- **Paths**: Validate paths are within library root (security)

**Reference**: See `ai-learnings.md` for detailed patterns with examples

## Testing & Quality
- Write tests regularly with pytest
- Handle cross-platform differences in mpv socket paths
- Validate metadata operations don't corrupt files
- Test graceful degradation when external services fail
- **Critical tests**: Data loss scenarios, atomic operations, ownership tracking
- **Edge cases**: Empty files, unsupported formats, duplicate tags, special characters
- **Performance**: Test with 1000+ items to verify batch operations and progress reporting

## Database Schema

### Current Version: v17
**Location**: `src/music_minion/core/database.py`

### Core Tables
- `tracks` - Music library metadata (artist, title, album, year, BPM, key, etc.)
  - **Multi-source support (v11+)**: Added `source` column ('local', 'soundcloud', 'spotify', 'youtube')
  - **Provider IDs (v11+)**: `soundcloud_id`, `spotify_id`, `youtube_id` for linking to provider tracks
  - **Path column (v11+, v14)**: Uses `local_path` column for local file storage
    - **Migration v14**: Removed legacy `file_path` column (backward compatibility no longer needed)
  - **Provider playlists (v12)**: `soundcloud_playlist_id`, `spotify_playlist_id`, `youtube_playlist_id`
  - **Sync tracking (v12)**: `last_track_count` for incremental provider sync
- `ratings` - User ratings with timestamps and context
  - **Provider like tracking (v17)**: Added `source` column ('user', 'soundcloud', 'spotify', 'youtube')
  - **Performance index (v17)**: `idx_ratings_track_source` for fast provider like lookups
- `tags` - Track tags with source tracking ('user', 'ai', 'file') and reasoning (v9)
- `notes` - Contextual notes about tracks

### Playlist System Tables (v3+)
- `playlists` - Manual and smart playlists
- `playlist_tracks` - Manual playlist track associations with position ordering
- `playlist_filters` - Smart playlist filter rules (field, operator, value, conjunction)
- `active_playlist` - Singleton table for active playlist state

### Playback & Sync Tables (v5+)
- `playback_state` - Singleton table for shuffle mode and position tracking
- Sync columns in `tracks`: `file_mtime`, `last_synced_at` for change detection

### Provider System Tables (v11+)
- `provider_state` - Stores OAuth tokens and provider-specific state (JSON blob)
- `active_library` - Singleton table for current active library ('local', 'soundcloud', etc.)

### AI Enhancements (v9)
- `tags.reasoning` - Stores AI reasoning for each tag (5-10 words)
- Supports conversational tag review and prompt improvement

### Migration Pattern
- Version-based migrations in `migrate_database()`
- Idempotent: Safe to run multiple times
- Use try/except for "duplicate column" errors

## Implementation Status

### ✅ Complete (Production-Ready)
- **Phase 1**: Core playlist infrastructure (manual playlists, CRUD, active playlist)
- **Phase 2**: Smart playlists with filter system (7 fields, 11 operators, AND/OR logic)
- **Phase 3**: AI natural language playlist parsing (OpenAI integration)
- **Phase 4**: Import functionality (M3U/M3U8/Serato .crate)
- **Phase 5**: Export functionality (M3U8/Serato with auto-export)
- **Phase 6**: Playback integration (shuffle mode, sequential navigation, position tracking)
- **Phase 7**: Bidirectional metadata sync (database ↔ file metadata, mtime tracking)
- **Architecture Refactor**: Reorganized to functional architecture with AppContext
  - Split flat structure into layered architecture (core, domain, commands, ui)
  - Migrated to blessed UI with pure functional approach
  - Implemented partial rendering for smooth, flicker-free updates
  - Added immutable state management with explicit context passing

### 🚧 Phase 8: Polish & Testing (Planned)
- File watching for real-time sync (watchdog library)
- Conflict detection UI
- Comprehensive test suite
- Performance monitoring
- Documentation

**Reference**: See `docs/playlist-system-plan.md` for detailed phase documentation

## Future Architecture Considerations
- Global hotkey support through background daemon
- Web UI for mobile control (localhost server)
- USB button controller integration
- Integration with existing players (playerctl/AppleScript)
- Spotify/streaming service integration

## Key Resources for Development

### Documentation
- **`ai-learnings.md`** - Patterns, best practices, and code review learnings
  - Critical sections: Data loss prevention, atomic operations, race conditions
  - Database patterns, error handling, threading
  - Import/export patterns, AI integration
  - UI component patterns (track viewer, wizard, review handler)

- **`docs/playlist-system-plan.md`** - Complete implementation history
  - Phases 1-7 with decisions, learnings, and time estimates
  - Known limitations and deferred items
  - Code review findings and bug fixes

- **`docs/incomplete-items.md`** - Future roadmap
  - Phase 8 tasks
  - Known limitations by phase
  - Recommendations for enhancements

- **`docs/ai-tag-review-system.md`** - AI review and prompt enhancement
  - Conversational tag feedback system
  - Learning accumulation and categorization
  - Prompt versioning and testing
  - Database schema v9 (reasoning field)

- **`docs/hot-reload-usage.md`** - Development mode guide
  - Hot-reload setup and usage
  - State preservation patterns
  - Troubleshooting and limitations

### Before Starting Work
1. Read `ai-learnings.md` for critical patterns
2. Check `docs/incomplete-items.md` for planned work
3. Review relevant phase in `docs/playlist-system-plan.md`
4. Understand database schema version and migrations

### Module Dependencies
```
main.py
  ├── context.py (AppContext dataclass)
  ├── router.py → commands/
  ├── helpers.py → context.py
  │
  ├── core/
  │   ├── database.py (lowest level)
  │   ├── config.py
  │   └── console.py
  │
  ├── domain/
  │   ├── library/
  │   │   ├── models.py
  │   │   ├── scanner.py → models.py
  │   │   └── metadata.py
  │   ├── playback/
  │   │   ├── state.py
  │   │   └── player.py → state.py
  │   ├── playlists/
  │   │   ├── crud.py → core/database.py
  │   │   ├── filters.py → core/database.py
  │   │   ├── ai_parser.py → filters.py
  │   │   ├── importers.py → crud.py
  │   │   └── exporters.py → crud.py
  │   ├── sync/
  │   │   └── engine.py → core/database.py
  │   └── ai/
  │       └── client.py
  │
  ├── commands/ (all take AppContext, return AppContext)
  │   ├── admin.py
  │   ├── ai.py → domain/ai/
  │   ├── playback.py → domain/playback/
  │   ├── playlist.py → domain/playlists/
  │   ├── rating.py → core/database.py
  │   ├── sync.py → domain/sync/
  │   └── track.py
  │
  └── ui/blessed/
      ├── app.py → state.py, components/, events/
      ├── state.py (UIState dataclass)
      ├── components/ → styles/
      ├── events/ → context.py, router.py
      └── styles/
```

**Rule**: Modules should only import from lower levels, no circular dependencies
**Pattern**: All command handlers take `AppContext` and return `(AppContext, bool)` for functional state updates

### Primary Use Case
**NYE 2025 DJ Set Preparation**: The playlist and sync systems were built for curating music on Linux (Music Minion) and DJing on Windows (Serato) with seamless bidirectional sync via Syncthing.

---

**Last Updated**: 2025-11-20 after SoundCloud like integration and provider refactoring (schema v17)