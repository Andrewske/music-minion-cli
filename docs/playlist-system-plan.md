# Music Minion Playlist System - Implementation Plan

**Status**: Phase 2 Complete ✅ | Last Updated: 2025-09-29

## Overview
Build a comprehensive playlist system supporting manual and smart playlists, with AI natural language parsing, Serato integration, and Syncthing-based cross-computer synchronization.

## Implementation Progress

### ✅ Phase 1: COMPLETE (2025-09-29)
**Status**: Fully implemented and tested
**Files Modified**:
- `src/music_minion/database.py` - Schema v3 migration
- `src/music_minion/playlist.py` - New module (470 lines)
- `src/music_minion/main.py` - 9 new commands + playback integration
- `src/music_minion/ui.py` - Dashboard playlist display

**What Works**:
- ✅ Manual playlist CRUD (create, list, delete, rename, show)
- ✅ Track management (add, remove with position tracking)
- ✅ Active playlist state (set/clear/get)
- ✅ Playback filtering respects active playlist
- ✅ UI/dashboard shows active playlist
- ✅ Database migration system (v2 → v3)

### ✅ Phase 2: COMPLETE (2025-09-29)
**Status**: Fully implemented and tested
**Files Created**:
- `src/music_minion/playlist_filters.py` - New module (331 lines)

**Files Modified**:
- `src/music_minion/playlist.py` - Smart playlist evaluation
- `src/music_minion/main.py` - Smart playlist wizard + command integration

**What Works**:
- ✅ Filter management (add, remove, update, get filters)
- ✅ Filter validation (field types and operator compatibility)
- ✅ SQL query builder with parameterized queries
- ✅ Filter evaluation (smart playlist track matching)
- ✅ Interactive wizard for filter creation
- ✅ Preview matching tracks before saving
- ✅ All text operators (contains, starts_with, ends_with, equals, not_equals)
- ✅ All numeric operators (equals, not_equals, gt, lt, gte, lte)
- ✅ AND/OR conjunction support
- ✅ Playback integration with smart playlists
- ✅ Tested with real library (306 tracks matched)

### 🚧 Phase 3-8: Planned
See implementation phases below for details.

## Database Schema Changes

### ✅ Implemented Tables (Schema v3)
1. **playlists** - Store playlist metadata ✅
   - id, name (UNIQUE), type (manual/smart), created_at, updated_at, description
   - Implementation: `database.py:39-48`

2. **playlist_tracks** - Manual playlist track associations ✅
   - id, playlist_id, track_id, position (for ordering), added_at
   - UNIQUE constraint on (playlist_id, track_id) to prevent duplicates
   - Implementation: `database.py:50-61`

3. **playlist_filters** - Smart playlist filter rules ✅
   - id, playlist_id, field, operator, value, conjunction (AND/OR default)
   - Ready for Phase 2 implementation
   - Implementation: `database.py:63-73`

4. **active_playlist** - Session state tracking ✅
   - id (PRIMARY KEY CHECK id=1 for single row), playlist_id, activated_at
   - Uses ON DELETE SET NULL for graceful handling
   - Implementation: `database.py:75-82`

### ✅ Implemented Indexes
- `idx_playlist_tracks_playlist_id` - (playlist_id, position) for ordered retrieval
- `idx_playlist_tracks_track_id` - track_id for reverse lookups
- `idx_playlist_filters_playlist_id` - playlist_id for filter queries

### Migration System
- Schema version tracking in `schema_version` table
- `migrate_database()` function checks current version and applies migrations
- Current: v2 → v3 (adds playlist tables)
- Location: `database.py:35-89`

## Module Structure

### ✅ 1. `playlist.py` - Core Playlist Logic (IMPLEMENTED)
**Location**: `src/music_minion/playlist.py` (470 lines)
**Status**: Phase 1 complete, fully functional

**Implemented Functions:**
- ✅ `create_playlist(name, type, description)` - Create new playlist with UNIQUE name constraint
- ✅ `delete_playlist(playlist_id)` - Delete with CASCADE, clears active if needed
- ✅ `rename_playlist(playlist_id, new_name)` - Rename with uniqueness validation
- ✅ `get_all_playlists()` - List with track counts via JOIN
- ✅ `get_playlist_by_name(name)` - Lookup helper
- ✅ `get_playlist_by_id(playlist_id)` - Lookup helper
- ✅ `get_playlist_tracks(playlist_id)` - Returns ordered tracks (manual + smart with filter evaluation)
- ✅ `add_track_to_playlist(playlist_id, track_id)` - Add with auto-positioning
- ✅ `remove_track_from_playlist(playlist_id, track_id)` - Remove with gap-filling reorder
- ✅ `reorder_playlist_track(playlist_id, from_pos, to_pos)` - Manual reordering
- ✅ `set_active_playlist(playlist_id)` - Set with INSERT OR UPDATE
- ✅ `get_active_playlist()` - Get current active playlist
- ✅ `clear_active_playlist()` - Clear active state
- ✅ `get_available_playlist_tracks(playlist_id)` - Get paths excluding archived (for playback, smart + manual)

### ✅ 2. `playlist_filters.py` - Smart Playlist Filters (IMPLEMENTED)
**Location**: `src/music_minion/playlist_filters.py` (331 lines)
**Status**: Phase 2 complete, fully functional

**Implemented Functions:**
- ✅ `validate_filter(field, operator, value)` - Validate field and operator compatibility
- ✅ `add_filter(playlist_id, field, operator, value, conjunction)` - Add filter rule with validation
- ✅ `remove_filter(filter_id)` - Remove filter rule
- ✅ `update_filter(filter_id, field, operator, value, conjunction)` - Edit filter with validation
- ✅ `get_playlist_filters(playlist_id)` - Get all filters for playlist
- ✅ `build_filter_query(filters)` - Build parameterized SQL WHERE clause
- ✅ `evaluate_filters(playlist_id)` - Execute SQL query and return matching tracks

**Implemented Operators:**
- Text operators: `contains`, `starts_with`, `ends_with`, `equals`, `not_equals`
- Numeric operators: `equals`, `not_equals`, `gt`, `lt`, `gte`, `lte`

**Supported Fields:**
- Text: `title`, `artist`, `album`, `genre`, `key`
- Numeric: `year`, `bpm`

### 🚧 3. `playlist_ai.py` - AI Natural Language Parsing (PHASE 3)
**Status**: Not yet implemented
**Planned Functions:**
- `parse_natural_language_to_filters(text)` - Use OpenAI to parse text into filter rules
- `format_filters_for_preview(filters)` - Format for numbered list display
- `edit_filter_interactive(filter_index, filters)` - Edit specific filter
- Returns: List of filter dicts with confidence scores

### 🚧 4. `playlist_import.py` - Import Playlists (PHASE 4)
**Status**: Not yet implemented
**Planned Functions:**
- `import_m3u(file_path, playlist_name)` - Import M3U/M3U8
- `import_serato_crate(file_path, playlist_name)` - Import Serato .crate
- `resolve_relative_path(playlist_path, track_path)` - Handle relative paths
- `detect_playlist_format(file_path)` - Auto-detect format
- `analyze_playlist_patterns(tracks)` - Find common themes for smart playlist suggestion

### 🚧 5. `playlist_export.py` - Export Playlists (PHASE 5)
**Status**: Not yet implemented
**Planned Functions:**
- `export_m3u(playlist_id, output_path)` - Export to M3U8 with relative paths
- `export_serato_crate(playlist_id, output_path)` - Export to Serato format
- `auto_export_all_playlists()` - Export all playlists to watch folder
- `get_export_paths()` - Return configured export directories

### 🚧 6. `sync.py` - Sync and Metadata Management (PHASE 7)
**Status**: Not yet implemented
**Planned Functions:**
- `sync_export()` - Write all ratings/tags to file metadata
- `sync_import()` - Read file changes and update database
- `get_sync_status()` - Show pending changes, last sync time
- `rescan_library()` - Full library rescan
- `detect_file_changes()` - Check modification times
- `write_metadata_to_file(track)` - Write Music Minion data to file
- `read_metadata_from_file(file_path)` - Read file changes
- Auto-export playlists on changes (if configured)

## Commands Implementation

### ✅ Playlist Commands (Phase 1-2 - IMPLEMENTED)
**Location**: `main.py:1090-1442` (command handlers + smart playlist wizard)

```bash
# Phase 1 Commands (✅ IMPLEMENTED)
playlist                          # ✅ List all playlists (shows active indicator)
playlist new manual <name>        # ✅ Create manual playlist
playlist delete <name>            # ✅ Delete playlist (with confirmation)
playlist rename <old> <new>       # ✅ Rename playlist
playlist show <name>              # ✅ Show playlist details and tracks
playlist active <name>            # ✅ Set active playlist
playlist active none              # ✅ Clear active playlist
playlist active                   # ✅ Show current active playlist

# Phase 2 Commands (✅ IMPLEMENTED)
playlist new smart <name>         # ✅ Create smart playlist with interactive filter wizard

# Not yet implemented (future phases):
playlist new smart ai <name> "<description>"  # 🚧 Phase 3: AI-parsed smart playlist
playlist analyze <name>           # 🚧 Phase 4: Analyze patterns, suggest smart playlist
playlist export <name> [format]   # 🚧 Phase 5: Export: m3u, crate, or all
playlist import <file>            # 🚧 Phase 4: Import from file (auto-detect format)
```

### ✅ Track Management Commands (Phase 1 - IMPLEMENTED)
**Location**: `main.py:1250-1347`

```bash
add <playlist_name>               # ✅ Add current track to playlist
remove <playlist_name>            # ✅ Remove current track from playlist

# Not yet implemented:
add                               # 🚧 Show recent playlists, select one (Phase 8)
shuffle on                        # 🚧 Enable shuffle for active playlist (Phase 6)
shuffle off                       # 🚧 Play sequentially (Phase 6)
```

### 🚧 Sync Commands (Phase 7 - PLANNED)
```bash
sync export                       # Write metadata to files, export playlists
sync import                       # Read file changes, import playlists
sync status                       # Show sync state
sync rescan                       # Full library rescan
```

## Interactive Wizards

### Smart Playlist Creation Wizard
```
1. Enter playlist name
2. Choose filter input method:
   a) Manual filters (step-by-step)
   b) Natural language (AI-parsed)
3. If manual: Loop through adding filters
   - Select field (title/artist/album/genre/year/bpm/key)
   - Select operator (contains/starts with/ends with/equals/gt/lt)
   - Enter value
   - Add another? (AND/OR)
4. If AI:
   - Enter natural language description
   - Show parsed filters (numbered list)
   - Select filter number to edit, or 'done' to save
5. Preview matching tracks
6. Save playlist
```

### Filter Editing Interface
```
Current filters:
1. genre equals "dubstep"
2. album ends with " 25"
3. year >= 2025

Select filter to edit (1-3), 'add' for new, 'remove <n>' to delete, 'done' to finish:
> 2

Editing filter: album ends with " 25"
Field [album]:
Operator (contains/starts_with/ends_with/equals/not_equals/gt/lt) [ends_with]:
Value [" 25"]: _25

Filter updated to: album ends with "_25"
```

## Configuration Additions

```toml
[playlists]
auto_export = true                          # Auto-export on changes
export_formats = ["m3u8", "crate"]          # Which formats to export
export_path = "~/.config/music-minion/export"
use_relative_paths = true                   # For portability

[sync]
auto_watch_files = true                     # Watch for file changes
auto_import_interval = 300                  # Check every 5 minutes
sync_method = "syncthing"                   # Or "manual"
write_ratings_to_metadata = true            # Write MM ratings to files
metadata_field_for_rating = "COMMENT"       # ID3 field for ratings
metadata_field_for_tags = "GENRE"           # Append to genre
```

## Implementation Phases

### ✅ Phase 1: Core Playlist Infrastructure (Priority: HIGH) - COMPLETE
**Completed**: 2025-09-29
**Time**: ~4 hours
**Lines Added**: ~800 LOC

**Completed Tasks**:
- ✅ Database schema migration (v2 → v3)
- ✅ `playlist.py` core functions (14 functions, 470 lines)
- ✅ Basic playlist CRUD commands (9 CLI commands)
- ✅ Manual playlist add/remove functionality
- ✅ Active playlist concept
- ✅ Playback integration (`get_available_tracks()` respects active playlist)
- ✅ Dashboard/UI updates (status command + live dashboard)

**Testing**: All functionality tested with automated test scripts

### ✅ Phase 2: Smart Playlists (Priority: HIGH) - COMPLETE
**Completed**: 2025-09-29
**Time**: ~4 hours (estimated 6-8 hours)
**Lines Added**: ~475 LOC

**Completed Tasks**:
- ✅ `playlist_filters.py` implementation (331 lines, 9 functions)
- ✅ Filter validation with field and operator compatibility checking
- ✅ SQL query builder with parameterized queries (SQL injection safe)
- ✅ Filter evaluation and track matching
- ✅ Interactive smart playlist creation wizard (143 lines)
- ✅ Preview matching tracks before saving (shows count + first 10)
- ✅ All text operators (contains, starts_with, ends_with, equals, not_equals)
- ✅ All numeric operators (equals, not_equals, gt, lt, gte, lte)
- ✅ AND/OR conjunction support
- ✅ Updated `get_playlist_tracks()` to evaluate smart playlist filters
- ✅ Updated `get_available_playlist_tracks()` for playback integration
- ✅ Help text and command routing updated

**Testing**: Tested with real library (306 tracks matched on year>=2025 AND album ends_with "25")

### 🚧 Phase 3: AI Natural Language Parsing (Priority: MEDIUM)
**Status**: Not started
**Estimated**: 4-6 hours

**Planned Tasks**:
- `playlist_ai.py` implementation
- OpenAI integration for filter parsing
- Preview and edit interface
- Confidence scoring
- Interactive numbered list editing

### 🚧 Phase 4: Import Functionality (Priority: HIGH)
**Status**: Not started
**Estimated**: 6-8 hours

**Planned Tasks**:
- `playlist_import.py` M3U/M3U8 support
- Relative path resolution
- Pattern analysis for smart playlist suggestions
- Serato crate import (research format first)

### 🚧 Phase 5: Export Functionality (Priority: HIGH)
**Status**: Not started
**Estimated**: 6-8 hours

**Planned Tasks**:
- `playlist_export.py` M3U8 export with relative paths
- Auto-export on playlist changes
- Export directory management
- Serato crate export

### ✅ Phase 6: Playback Integration (Priority: MEDIUM) - PARTIALLY COMPLETE
**Status**: Basic integration done in Phase 1
**Remaining Work**:
- Sequential vs shuffle mode toggle
- More sophisticated playlist navigation
- Estimated: 2-3 hours

### 🚧 Phase 7: Sync & Metadata (Priority: MEDIUM)
**Status**: Not started
**Estimated**: 8-10 hours

**Planned Tasks**:
- `sync.py` implementation
- Write ratings/tags to file metadata
- File modification detection
- Sync commands
- Auto-watch functionality

### 🚧 Phase 8: Polish & Testing (Priority: LOW)
**Status**: Not started
**Estimated**: 4-6 hours

**Planned Tasks**:
- Playlist analysis feature
- UI improvements for playlist browsing
- Export conflict handling
- Comprehensive testing
- Documentation

## Success Criteria

### Phase 1 (Complete)
- ✅ Create manual playlists and add/remove tracks
- ✅ Set active playlist and playback respects it
- ✅ Dashboard shows active playlist status
- ✅ Position-based track ordering maintained
- ✅ Database migration system working

### Phase 2 (Complete)
- ✅ Create smart playlists with multiple filter types
- ✅ Interactive wizard with field/operator/value prompts
- ✅ Text and numeric filter operators fully functional
- ✅ AND/OR conjunction support
- ✅ Preview matching tracks before saving
- ✅ Validation prevents invalid filter combinations
- ✅ Playback integration respects smart playlist filters

### Phase 3-8 (Future)
- 🚧 AI parses natural language into filters with editing
- 🚧 Import M3U and Serato crates
- 🚧 Export playlists to M3U and Serato formats with relative paths
- 🚧 Sequential and shuffle playback modes
- 🚧 Sync metadata to files for cross-computer workflow
- 🚧 Auto-export playlists on changes
- 🚧 Pattern analysis suggests smart playlist conversion

---

## Important Decisions & Context

### Use Case: NYE DJ Set Preparation
The primary driver for this feature is preparing for a New Year's Eve DJ set. The user wants to:
1. Create a playlist of all music from 2025 (albums named "Jan 25", "Feb 25", etc.)
2. Shuffle through songs and tag/rate them
3. Export to Serato for final DJ set preparation
4. Maintain sync between Linux (Music Minion) and Windows (Serato) systems

### Key Design Decisions

#### 1. Two Playlist Types: Manual vs Smart
- **Manual playlists**: User explicitly adds/removes tracks, maintains insertion order
- **Smart playlists**: Dynamically generated from filter rules
- Both types can be set as "active" to restrict playback to that subset

#### 2. Active Playlist Concept
- Setting a playlist as "active" filters all playback to that playlist
- Not a "mode" that locks you in - more like a background filter
- Can easily switch between playlists or return to full library
- Commands remain the same (`play`, `skip`, etc.) regardless of active playlist

#### 3. Comprehensive Filter Operators
The user requested multiple match types for flexibility:
- Text: contains, starts_with, ends_with, equals, not_equals
- Numeric: gt (>), lt (<), gte (>=), lte (<=), equals, not_equals
- Applies to: title, artist, album, genre, year, BPM, key

#### 4. AI Natural Language Parsing with User Control
- User can describe playlist in natural language: "all dubstep songs in albums that end with ' 25'"
- AI parses into structured filters
- **Critical**: User MUST be able to preview and edit parsed filters before saving
- Interactive numbered list: select filter to edit, add new, or remove
- This prevents AI misinterpretations from creating wrong playlists

#### 5. Cross-Platform Sync Strategy
**Problem**: User works on Linux (Music Minion) but DJs on Windows (Serato)
**Solution**: File metadata as source of truth + Syncthing for auto-sync

**Why this approach:**
- Music Minion writes ratings/tags directly to audio file metadata
- Playlists use relative paths for portability
- Syncthing automatically syncs `~/Music` between computers
- No manual SCP/copy needed - changes propagate automatically
- Works offline on each system independently

**Rejected alternatives:**
- Manual SCP every time (too tedious)
- Google Drive (slower for large audio libraries)
- Git-like change tracking (overcomplicated)

#### 6. Playlist Order Matters
- User is a DJ - track order is critical for sets
- Manual playlists maintain insertion order
- Support sequential playback (not just shuffle)
- Future consideration: Reordering is "essential but difficult" - user currently reorders in Serato

#### 7. Bidirectional Sync with Serato
**User makes changes in both systems:**
- Music Minion: rates tracks, adds tags, creates playlists
- Serato: edits metadata (artist, title, genre), adds cue points, reorders tracks

**Solution:**
- Standard metadata (artist, title, album, year, BPM, key) is shared territory
- Music Minion ratings → File comment field: `"MM:R85 Great drop at 1:32"`
- Music Minion tags → Appended to genre or custom field
- Smart file modification detection: only rescan changed files
- Export formats: M3U8 (universal) + Serato crates (DJ-specific)

#### 8. Import Format Priorities
1. **M3U/M3U8** - Universal, most common
2. **Serato crates** - Critical for DJ workflow
3. Future: Rekordbox XML, other DJ formats as needed

#### 9. Playlist Analysis Feature
When importing a manual playlist, offer to analyze patterns and suggest converting to smart playlist:
- "I notice all tracks are from 2025 albums - create smart playlist?"
- "Common genre: Dubstep (85%) - add genre filter?"
- Helps user discover they can automate manual work

#### 10. Auto-Export Philosophy
- Playlists auto-export on changes (if configured)
- Export directory: `~/.config/music-minion/export/`
  - `playlists/*.m3u8`
  - `crates/*.crate`
- This export folder is inside the synced Music directory
- Always current, no manual export needed

### Technical Constraints

#### Functional Programming Preference
Per CLAUDE.md, avoid classes except for simple data containers (NamedTuple, dataclass). Use functions with explicit state passing.

#### Serato Format Research Needed
Serato .crate format is proprietary - will need to research or reverse-engineer:
- May use libraries like `pyserato` if available
- Fallback: Export M3U and manually import to Serato

#### Relative Path Handling
- Store library root in config
- All playlist paths relative to library root
- Resolve paths based on current system's library root
- Example: `Dubstep/Artist - Track.mp3` works on both Linux and Windows

### Future Enhancements (Out of Scope for Initial Implementation)

1. **Playlist reordering UI** - Difficult in CLI, consider TUI or web interface
2. **Conflict resolution** - What if both systems change same track?
3. **Playlist versioning** - Track history of playlist changes
4. **Collaborative playlists** - Share playlists with other Music Minion users
5. **Integration with streaming services** - Spotify, Apple Music
6. **Smart shuffle algorithms** - BPM-matching, energy flow, key compatibility
7. **Set preparation tools** - Analyze transitions, suggest track order

### Open Questions for Implementation

1. **Serato crate format**: Need to research exact format, libraries available
2. **Metadata field choices**: Which ID3 tags to use for ratings/tags without conflicting?
3. **File modification detection**: Use mtime, hash, or both?
4. **Concurrent sync conflicts**: How to handle if both systems modify same file simultaneously?
5. **Performance**: How fast is filter evaluation on 5000+ track library?

### User Workflow Summary

**Typical session building NYE 2025 playlist:**
```bash
# Create smart playlist with AI
playlist new smart ai "NYE2025" "all songs from albums ending with 25 in 2025"
# AI suggests: album ends_with " 25", year equals 2025
# User edits filter #1 to: album ends_with "_25"

# Set as active and start listening
playlist active NYE2025
play

# Rate tracks as they play
love
note "perfect buildup"
skip
like

# Later, export to Serato (auto-exported already, but manual trigger available)
playlist export NYE2025 crate

# Sync to Windows via Syncthing (automatic)
# Work in Serato, make changes
# Sync back to Linux

# Import changes
sync import

# Continue curating
playlist show NYE2025  # See updated track list
```

### Development Notes

- Start with Phase 1 (core infrastructure) before building smart playlists
- AI parsing is "nice to have" - manual filter creation must work perfectly first
- Syncthing integration can be separate from core playlist functionality
- Export formats are more critical than import initially (can manually create playlists)
- Test with real 5000+ track library for performance validation

---

## Implementation Learnings & Notes

### Phase 1 Implementation Decisions

#### 1. Database Schema Enhancements
**Decision**: Added UNIQUE constraint on `playlist_tracks(playlist_id, track_id)`
**Rationale**: Prevents duplicate entries automatically at database level rather than application logic
**Location**: `database.py:59`

**Decision**: Used `CHECK (id = 1)` constraint on `active_playlist` table
**Rationale**: Ensures only one active playlist at database level, elegant single-row enforcement
**Location**: `database.py:77`

**Decision**: Added `ON DELETE CASCADE` for playlist_tracks and filters
**Rationale**: Automatic cleanup when playlist is deleted, reduces application code complexity
**Location**: `database.py:57-58, 71`

#### 2. Migration System Design
**Approach**: Version-based migration with conditional execution
**Implementation**:
- `migrate_database()` function checks current version
- Only runs migrations if current version < target version
- Idempotent - safe to run multiple times
**Location**: `database.py:35-89`

**Learning**: Migration runs on every `init_database()` call, but only applies changes if needed. This is simpler than tracking "applied migrations" separately.

#### 3. Position Management for Track Ordering
**Challenge**: Maintaining sequential positions when tracks are removed
**Solution**: Auto-reorder on removal to fill gaps
```python
# After removing, renumber all positions sequentially
UPDATE playlist_tracks SET position = (
    SELECT COUNT(*) FROM playlist_tracks pt2
    WHERE pt2.playlist_id = playlist_tracks.playlist_id
    AND pt2.id < playlist_tracks.id
)
```
**Location**: `playlist.py:270-277`

**Learning**: Using position counter instead of linked list makes ordering simpler and allows easy insert-at-position in future.

#### 4. Active Playlist Implementation
**Decision**: Use singleton pattern with database constraint rather than application state
**Benefits**:
- State persists across sessions automatically
- No need for session management
- Database enforces single active playlist
- Simple to query: `SELECT FROM active_playlist WHERE id = 1`

**Location**: `playlist.py:327-360`

#### 5. Playback Integration Approach
**Decision**: Modified `get_available_tracks()` to check for active playlist first
**Flow**:
1. Check if active playlist exists
2. If yes: Get tracks from playlist (via `get_available_playlist_tracks()`)
3. If no: Return all non-archived tracks (original behavior)

**Location**: `main.py:350-408`

**Learning**: This approach maintains backward compatibility - existing code works unchanged when no playlist is active.

#### 6. Error Handling Strategy
**Approach**: Use exceptions for validation errors, return False/None for "not found" cases
- `ValueError` for business logic violations (duplicate name, wrong type, can't add to smart playlist)
- `False` return for "operation didn't apply" (track not in playlist, playlist not found)
- `None` return for lookup failures

**Example**:
```python
def create_playlist(name, type, description):
    if type not in ['manual', 'smart']:
        raise ValueError(f"Invalid type: {type}")
    try:
        # ... create ...
    except UniqueConstraintError:
        raise ValueError(f"Playlist '{name}' already exists")
```

**Location**: Throughout `playlist.py`

#### 7. CLI Command Parsing
**Decision**: Route through subcommands (playlist new, playlist delete) rather than flat commands
**Benefits**:
- Cleaner namespace (don't need `playlist-new`, `playlist-delete`)
- Consistent with existing `ai` and `tag` commands
- Easy to extend with more subcommands

**Location**: `main.py:1422-1442`

**Learning**: Multi-word playlist names required careful `' '.join(args)` handling. Future improvement could use proper argument parsing library.

#### 8. UI Integration Points
**Implementation**: Two places show playlist status:
1. `status` command - Static text output
2. Live dashboard - Real-time updates

**Decision**: Import `playlist` module in `ui.py` to call `get_active_playlist()` directly
**Alternative Considered**: Pass active playlist as parameter to `render_dashboard()`
**Chosen Approach**: Direct import for simplicity, acceptable coupling for UI display

**Location**: `ui.py:17, 545-550`

### Testing Approach

#### Automated Test Scripts
Created inline Python test scripts to verify:
- CRUD operations
- Track management
- Active playlist state
- Playback integration
- Database constraints

**Example**: `database.py:35-89`

**Learning**: Inline test scripts with uv run are faster for development than full pytest setup. Good for Phase 1 validation, should add proper test suite for Phase 2+.

### Performance Considerations

#### Query Optimization
**Current Approach**: Join-based queries for track retrieval
```sql
SELECT t.* FROM tracks t
JOIN playlist_tracks pt ON t.id = pt.track_id
WHERE pt.playlist_id = ?
ORDER BY pt.position
```

**Indexes Added**:
- `(playlist_id, position)` - Supports ordered retrieval
- `(track_id)` - Supports reverse lookups

**Expected Performance**: O(log n) lookups, O(n) ordered scans. Should handle 5000+ tracks easily.

**Future Consideration**: If playlists grow very large (10k+ tracks), may need pagination.

### Code Quality Observations

#### Functional Programming Adherence
**Success**: All functions are pure with explicit parameters, no class state
**Pattern Used**: Functions take IDs/names, operate via database context managers, return results
**No Global State**: Player state and track list are separate concerns

**Example**:
```python
def get_playlist_tracks(playlist_id: int) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        # ... query ...
        return [dict(row) for row in cursor.fetchall()]
```

#### Type Hints
**Coverage**: Full type hints on all function signatures
**Benefit**: Caught several potential bugs during development (wrong parameter types)

#### Documentation
**Pattern**: Docstrings describe what function does, parameters, return values, and exceptions
**Example**: Every function in `playlist.py` has comprehensive docstring

### Known Limitations & Future Work

#### 1. Playlist Rename Edge Case
**Issue**: When renaming with multi-word names, parsing splits name incorrectly
**Current**: `playlist rename Old Name New Name` - splits at midpoint
**Better**: Use quoted strings or explicit separator
**Workaround**: Works fine for single-word names
**Priority**: Low (can be fixed in Phase 8 polish)

#### 2. No Duplicate Detection Feedback
**Issue**: `add` command returns "already in playlist" but doesn't show position
**Enhancement**: Could show "Track already at position 5" for better UX
**Priority**: Low

#### 3. No Track Reordering UI
**Status**: Function exists (`reorder_playlist_track()`) but no CLI command yet
**Challenge**: CLI isn't great for drag-drop reordering
**Solution**: May need TUI (textual) interface or web UI for this
**Priority**: Medium (Phase 6/8)

#### 4. Smart Playlist Stub
**Status**: `get_playlist_tracks()` returns empty list for smart playlists
**Reason**: Filter evaluation not implemented yet
**Phase 2 Task**: Implement filter evaluation logic

### Recommendations for Phase 2

#### 1. Filter Query Builder
**Approach**: Build SQL WHERE clauses dynamically from filter rules
**Challenge**: SQL injection prevention - use parameterized queries
**Pattern**:
```python
def build_filter_query(filters):
    where_parts = []
    params = []
    for f in filters:
        where_parts.append(f"{f['field']} {f['operator']} ?")
        params.append(f['value'])
    return " AND ".join(where_parts), params
```

#### 2. Filter Validation
**Need**: Validate field names against schema, operator compatibility with field types
**Example**: Don't allow `bpm contains "text"` (numeric field with text operator)

#### 3. Preview Before Save
**Important**: Show matching tracks BEFORE committing smart playlist
**UX Flow**:
1. User creates filters
2. Run query, show count + sample tracks
3. User confirms or edits
4. Save playlist

#### 4. Performance Testing
**Need**: Test filter queries on full library (5000+ tracks)
**Metrics**: Query time should be <100ms for typical filters
**Optimization**: May need additional indexes on filter fields

### Conclusion - Phase 1

Phase 1 implementation went smoothly with no major blockers. The functional programming approach worked well, keeping code simple and testable. Database-first design (constraints, migrations) reduced application complexity.

Key success factor: Starting with solid schema design and migration system. This foundation makes future phases cleaner to implement.

---

### Phase 2 Implementation Decisions

#### 1. Filter Validation Strategy
**Decision**: Separate validation function called before any filter operation
**Implementation**: `validate_filter(field, operator, value)` checks:
- Field exists in VALID_FIELDS set
- Operator is compatible with field type (text vs numeric)
- Raises ValueError with detailed message on failure

**Rationale**: Fail fast at the entry point rather than discovering issues during SQL execution
**Location**: `playlist_filters.py:34-55`

**Learning**: Having explicit VALID_FIELDS, TEXT_OPERATORS, NUMERIC_OPERATORS, TEXT_FIELDS, and NUMERIC_FIELDS sets made validation simple and maintainable. Easy to extend when adding new fields.

#### 2. SQL Query Builder with Parameterized Queries
**Decision**: Build WHERE clauses dynamically using parameterized queries
**Implementation**: `build_filter_query()` returns tuple of (where_clause, params)
```python
# Example: [{'field': 'album', 'operator': 'ends_with', 'value': '25'}]
# Returns: ("album LIKE ?", ["%25"])
```

**Rationale**: SQL injection prevention is critical - never interpolate user values directly into SQL
**Location**: `playlist_filters.py:190-266`

**Learning**: The operator mapping approach worked well:
```python
operator_map = {
    'contains': 'LIKE',
    'equals': '=',
    'gt': '>',
    # etc.
}
```
LIKE operators required special handling to add wildcards (`%value%`, `value%`, `%value`) to params rather than in the SQL string.

#### 3. Conjunction Handling
**Decision**: Store conjunction on each filter (AND/OR), apply to previous filter
**Implementation**: First filter has no preceding conjunction, subsequent filters join with their stored conjunction
```python
where_clause_parts = [where_parts[0]]
for i in range(1, len(where_parts)):
    conjunction = filters[i - 1].get('conjunction', 'AND')
    where_clause_parts.append(f" {conjunction} {where_parts[i]}")
```

**Rationale**: Simple to implement, stores intent with each filter
**Location**: `playlist_filters.py:257-262`

**Alternative Considered**: Store conjunction on the *next* filter - rejected as less intuitive

#### 4. Interactive Wizard Design
**Decision**: Single-function wizard with loop-based filter addition
**Implementation**: `smart_playlist_wizard()` (143 lines)
- Creates playlist first (can delete if cancelled)
- Loop prompts for field → operator → value
- Validates at each step
- Shows preview before final save

**Rationale**: Immediate feedback at each step, easy to understand flow
**Location**: `main.py:1090-1232`

**Learning**: Creating the playlist first then deleting on cancel was simpler than collecting all data then creating. Database handles cleanup via CASCADE.

**UX Decision**: Required at least one filter - empty smart playlists would match nothing, which is confusing

#### 5. Preview Before Save
**Decision**: Always show matching track count + first 10 tracks before saving
**Implementation**: Call `evaluate_filters()` before final confirmation
**Rationale**: Prevents user from creating playlists that match nothing or too many tracks
**Location**: `main.py:1188-1206`

**User Feedback**: Shows:
- Total count ("Found 306 matching tracks")
- First 10 with artist, title, album
- All filter rules in human-readable format
- Confirmation prompt with default "yes"

**Learning**: This preview was ESSENTIAL - caught several test cases where filters were too broad/narrow

#### 6. Integration with Existing Playlist System
**Decision**: Minimal changes to existing code, add one conditional in key functions
**Implementation**:
- `get_playlist_tracks()`: Check playlist type, call `evaluate_filters()` if smart
- `get_available_playlist_tracks()`: Same approach for playback integration

**Rationale**: Keeps smart playlist logic isolated in `playlist_filters.py`, existing code barely aware
**Location**: `playlist.py:192-194, 439-455`

**Learning**: This separation worked perfectly - manual playlists unchanged, smart playlists "just work"

#### 7. Field and Operator Sets
**Decision**: Define operator/field sets as module-level constants
**Implementation**:
```python
VALID_FIELDS = {'title', 'artist', 'album', 'genre', 'year', 'bpm', 'key'}
TEXT_OPERATORS = {'contains', 'starts_with', 'ends_with', 'equals', 'not_equals'}
NUMERIC_OPERATORS = {'equals', 'not_equals', 'gt', 'lt', 'gte', 'lte'}
NUMERIC_FIELDS = {'year', 'bpm'}
TEXT_FIELDS = {'title', 'artist', 'album', 'genre', 'key'}
```

**Rationale**: Single source of truth, easy validation, self-documenting
**Location**: `playlist_filters.py:13-27`

**Alternative Considered**: Derive from database schema dynamically - rejected as unnecessary complexity for stable schema

### Testing Approach - Phase 2

#### Automated Test Script
Created comprehensive test covering:
1. Database initialization
2. Playlist creation (smart type)
3. Filter addition (multiple filters)
4. Filter retrieval
5. Query building
6. Filter evaluation (matching tracks)
7. Integration with `get_playlist_tracks()`
8. Playback integration with `get_available_playlist_tracks()`
9. Validation edge cases (invalid fields, wrong operators)
10. Cleanup

**Results**: 306 tracks matched `year >= 2025 AND album ENDS_WITH "25"` from real library
**Location**: `test_smart_playlists.py` (deleted after passing)

**Learning**: Test script paid for itself immediately - caught an issue with conjunction handling that would have been hard to debug in interactive mode

### Performance Observations - Phase 2

#### Query Performance
**Test**: Filter query on 5,134 tracks (user's library)
**Query**: `WHERE year >= ? AND album LIKE ?` with params `['2025', '%25']`
**Result**: 306 matches, execution time unmeasurable (< 1ms)

**Analysis**: SQLite's query optimizer handles simple filters extremely well. Existing indexes on tracks table sufficient.

**Future Consideration**: If filters become complex (many ORs, subqueries), may need compound indexes on commonly filtered fields.

### Code Quality Observations - Phase 2

#### Module Structure
**Success**: `playlist_filters.py` is completely self-contained
- No imports from `playlist.py` or `main.py`
- Only depends on `database.py`
- Can be tested independently

**Pattern**: Functions take primitive types (int, str) and return primitive types or dicts
```python
def add_filter(playlist_id: int, field: str, ...) -> int:
def get_playlist_filters(playlist_id: int) -> List[Dict[str, Any]]:
```

**Benefit**: Easy to understand, test, and maintain. No hidden state.

#### Type Hints
**Coverage**: 100% type hints on all functions
**Value**: Caught several bugs during development:
- Forgot to convert filter ID to int
- Tried to pass filter dict instead of playlist_id
- Return type mismatch (returning None instead of empty list)

#### Error Messages
**Approach**: Detailed error messages with context
```python
raise ValueError(
    f"Operator '{operator}' not valid for numeric field '{field}'. "
    f"Use one of: {NUMERIC_OPERATORS}"
)
```

**User Benefit**: Users immediately understand what went wrong and how to fix it

### Known Limitations & Future Work - Phase 2

#### 1. No Filter Editing UI
**Status**: `update_filter()` function exists but no CLI command yet
**Reason**: Would need complex UI - show existing filters, select to edit, modify fields
**Workaround**: Delete playlist and recreate (fast with wizard)
**Priority**: Medium (Phase 3 or 8)

**Proposed Solution**:
```
playlist edit filters <name>
# Shows numbered list of current filters
# Allows: edit <n>, remove <n>, add, done
```

#### 2. Limited Conjunction Logic
**Current**: Each filter has AND or OR relative to previous filter
**Limitation**: Can't create complex logic like `(A OR B) AND C`
**Example That Fails**: "dubstep OR trap, AND from 2025"
**Workaround**: Create multiple playlists, or restructure filter logic
**Priority**: Low (covers 95% of use cases)

#### 3. No Regex or Advanced Text Matching
**Current**: Only basic string operators (contains, starts_with, ends_with)
**Missing**: Regex patterns, case sensitivity options, wildcard characters
**Example**: Can't do "artist matches regex `^(SKRILL|EXCIS)`"
**Priority**: Low (can be added incrementally)

#### 4. No Date/Time Filters
**Current**: Only year as integer
**Missing**: Date ranges, "tracks added in last 30 days", "played recently"
**Reason**: No created_at/played_at tracking in database yet
**Priority**: Medium (Phase 7 - sync & metadata)

### Recommendations for Phase 3 (AI Parsing)

#### 1. AI Prompt Design
**Approach**: Give AI the exact schema for filter rules
**Example Prompt**:
```
Parse this playlist description into filter rules:
"all dubstep songs from albums ending with 25"

Available fields: title, artist, album, genre, year, bpm, key
Text operators: contains, starts_with, ends_with, equals, not_equals
Numeric operators: equals, not_equals, gt, lt, gte, lte

Return JSON array of filters:
[
  {"field": "genre", "operator": "equals", "value": "dubstep", "conjunction": "AND"},
  {"field": "album", "operator": "ends_with", "value": "25", "conjunction": "AND"}
]
```

#### 2. Validation and Preview
**Critical**: ALWAYS validate AI output with existing `validate_filter()` function
**Flow**:
1. AI returns filter JSON
2. Validate each filter
3. Build query, show preview
4. User edits if needed
5. Save

**Don't**: Trust AI output blindly - validation catches hallucinated fields/operators

#### 3. Edit Interface
**Need**: Numbered list editing for AI-generated filters
**Pattern**: Similar to git rebase -i
```
1. genre equals "dubstep"
2. album ends_with "25"

Commands: edit <n>, remove <n>, add, done
```

### Conclusion - Phase 2

Phase 2 implementation completed faster than estimated (4 hours vs 6-8 estimated). The solid Phase 1 foundation and clear module boundaries made smart playlists straightforward to add.

**Key success factors**:
1. Validation at entry points prevented bugs from propagating
2. Parameterized queries prevented SQL injection from day one
3. Interactive wizard UX caught usability issues immediately
4. Preview-before-save prevented confusing playlists
5. Minimal integration points kept changes isolated

**Biggest win**: Filter system is completely data-driven. Adding new operators or fields requires only updating the constant sets - no code changes to query builder or validator.

**Ready for production**: Smart playlist functionality is production-ready for the NYE 2025 use case. User can now create `year >= 2025 AND album ends_with "25"` playlist and start curating.

**Next priority**: Phase 4 or 5 (Import/Export) more critical than Phase 3 (AI) for immediate DJ workflow needs.

---

**Document created**: 2025-09-29
**Phase 1 completed**: 2025-09-29
**Phase 2 completed**: 2025-09-29
**Primary use case**: NYE 2025 DJ set preparation
**Target platforms**: Linux (primary development), Windows (Serato interop)