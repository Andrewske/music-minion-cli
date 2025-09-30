# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
Music Minion CLI is a contextual music curation tool that learns user preferences over time. It focuses on capturing temporal patterns (when you like songs) rather than static ratings, building a "music minion" that understands your taste evolution.

## Architecture & Design Principles

### Core Architecture
- **Functional over Classes**: Use functions and modules, avoid complex class hierarchies. **CRITICAL**: Always question if a class is necessary - prefer functions with explicit state passing over classes with instance variables. Only use classes for simple data containers (NamedTuple, dataclass) or when there's compelling justification that must be explicitly provided and approved.
- **Single Responsibility**: Each function ≤20 lines, ≤3 nesting levels
- **Fail Fast**: Critical errors (missing mpv, no music) should exit with clear messages
- **Graceful Degradation**: Non-critical errors (AI failures, corrupted files) should log and continue

### Project Structure
```
music-minion/
├── src/music_minion/
│   ├── __init__.py
│   ├── main.py                 # Entry point and interactive loop
│   ├── player.py               # mpv integration and control
│   ├── library.py              # Music scanning and metadata
│   ├── database.py             # SQLite operations (schema v7)
│   ├── ai.py                   # OpenAI integration
│   ├── config.py               # Configuration loading (TOML)
│   ├── ui.py                   # Terminal display and formatting
│   ├── playlist.py             # Playlist CRUD operations
│   ├── playlist_filters.py     # Smart playlist filter logic
│   ├── playlist_ai.py          # AI natural language parsing
│   ├── playlist_import.py      # Import M3U/Serato playlists
│   ├── playlist_export.py      # Export to M3U8/Serato formats
│   ├── playback.py             # Playback state management
│   └── sync.py                 # Bidirectional metadata sync
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
- **rich/textual**: Terminal UI and progress bars
- **pathlib**: Cross-platform path handling
- **tomllib**: TOML configuration loading (Python 3.11+)
- **pyserato**: Serato .crate file import/export for DJ integration
- **sqlite3**: Database operations (built-in)

### Entry Points
- Primary command: `music-minion`
- Interactive mode with commands: `play`, `love`, `skip`, `note "text"`
- Setup command: `music-minion init`

## Key Technical Decisions

### Audio Integration
- **MPV with JSON IPC** for cross-platform audio playback
- Handles complex audio processing while focusing on curation logic
- Socket-based communication for control from anywhere

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
- `like` - Basic positive rating
- `love` - Strong positive rating
- `note "text"` - Add contextual notes

### AI Integration Commands
- `ai setup <key>` - Configure OpenAI API key
- `ai analyze library` - Batch process existing library
- `ai process batch` - Process accumulated unprocessed songs

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

### Context Tracking
- Store ratings with timestamp and context (time of day, day of week)
- Track preference patterns and evolution over time
- Mood correlation and session statistics
- Bidirectional sync with file metadata (Linux ↔ Windows/Serato)

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

## Critical Patterns & Best Practices

### Data Loss Prevention
**CRITICAL**: When implementing bidirectional sync or any data removal:
- Always track data ownership/source (`source='user'`, `source='ai'`, `source='file'`)
- NEVER remove data without checking ownership
- Only remove data you own (e.g., only remove `source='file'` tags during import)
- See `ai-learnings.md` section "Data Loss Prevention Through Ownership Tracking"

### Atomic File Operations
**CRITICAL**: All file writes must be atomic:
```python
temp_path = file_path + '.tmp'
try:
    audio.save(temp_path)
    os.replace(temp_path, file_path)  # Atomic on Unix/Windows
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

### Current Version: v7
**Location**: `src/music_minion/database.py`

### Core Tables
- `tracks` - Music library metadata (artist, title, album, year, BPM, key, etc.)
- `ratings` - User ratings with timestamps and context
- `tags` - Track tags with source tracking ('user', 'ai', 'file')
- `notes` - Contextual notes about tracks

### Playlist System Tables (v3+)
- `playlists` - Manual and smart playlists
- `playlist_tracks` - Manual playlist track associations with position ordering
- `playlist_filters` - Smart playlist filter rules (field, operator, value, conjunction)
- `active_playlist` - Singleton table for active playlist state

### Playback & Sync Tables (v5+)
- `playback_state` - Singleton table for shuffle mode and position tracking
- Sync columns in `tracks`: `file_mtime`, `last_synced_at` for change detection

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

- **`docs/playlist-system-plan.md`** - Complete implementation history
  - Phases 1-7 with decisions, learnings, and time estimates
  - Known limitations and deferred items
  - Code review findings and bug fixes

- **`docs/incomplete-items.md`** - Future roadmap
  - Phase 8 tasks
  - Known limitations by phase
  - Recommendations for enhancements

### Before Starting Work
1. Read `ai-learnings.md` for critical patterns
2. Check `docs/incomplete-items.md` for planned work
3. Review relevant phase in `docs/playlist-system-plan.md`
4. Understand database schema version and migrations

### Module Dependencies
```
main.py
  ├── database.py (lowest level)
  ├── config.py
  ├── sync.py → database.py
  ├── playlist.py → database.py
  ├── playlist_filters.py → database.py
  ├── playlist_ai.py → ai.py, playlist_filters.py
  ├── playlist_import.py → playlist.py, database.py
  ├── playlist_export.py → playlist.py, database.py
  └── playback.py → database.py
```

**Rule**: Modules should only import from lower levels, no circular dependencies

### Primary Use Case
**NYE 2025 DJ Set Preparation**: The playlist and sync systems were built for curating music on Linux (Music Minion) and DJing on Windows (Serato) with seamless bidirectional sync via Syncthing.

---

**Last Updated**: 2025-09-29 after Phase 7 completion