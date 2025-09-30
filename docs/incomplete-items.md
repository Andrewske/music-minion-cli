# Incomplete Items & Future Enhancements

**Created**: 2025-09-29
**Status**: Extracted from playlist-system-plan.md
**Current Phase**: Phase 7 Complete, Phase 8 Planned

This document tracks incomplete features, known limitations, and planned enhancements for Music Minion CLI.

---

## Phase 8: Polish & Testing (Not Started)

### Planned Tasks

1. **Playlist Analysis Feature**
   - Analyze imported manual playlists for patterns
   - Suggest smart playlist conversion
   - Example: "I notice all tracks are from 2025 albums - create smart playlist?"
   - Implementation: `analyze_playlist_patterns(tracks)` in `playlist_import.py`

2. **UI Improvements**
   - Playlist browsing enhancements
   - Visual progress bars for long operations
   - Format: `[####------] 40% (2000/5000)`
   - Use Rich library for progress bars

3. **Export Conflict Handling**
   - Detect conflicts when both DB and file changed
   - Prompt user: "Keep [F]ile, [D]atabase, or [M]erge?"
   - Show diff between conflicting versions

---

## Known Limitations by Phase

### Phase 2: Smart Playlists

#### 1. No Filter Editing UI
- **Current**: `update_filter()` function exists but no CLI command
- **Workaround**: Delete playlist and recreate with wizard
- **Proposed Solution**:
  ```bash
  playlist edit filters <name>
  # Shows numbered list, allows: edit <n>, remove <n>, add, done
  ```
- **Priority**: Medium (Phase 8)

#### 2. Limited Conjunction Logic
- **Current**: Each filter has AND or OR relative to previous
- **Limitation**: Can't create complex logic like `(A OR B) AND C`
- **Example That Fails**: "dubstep OR trap, AND from 2025"
- **Workaround**: Create multiple playlists or restructure logic
- **Priority**: Low (covers 95% of use cases)

#### 3. No Regex or Advanced Text Matching
- **Current**: Only basic operators (contains, starts_with, ends_with)
- **Missing**: Regex patterns, case sensitivity options, wildcard characters
- **Example**: Can't do "artist matches regex `^(SKRILL|EXCIS)`"
- **Priority**: Low (can be added incrementally)

#### 4. No Date/Time Filters
- **Current**: Only year as integer
- **Missing**: Date ranges, "tracks added in last 30 days", "played recently"
- **Reason**: No created_at/played_at tracking in database yet
- **Priority**: Medium (useful for curation workflow)

### Phase 4 & 5: Import/Export

#### 1. No Serato Metadata Preservation
- **Current**: Import/export only handles track paths
- **Missing**: Cue points, hot cues, beatgrids, loops
- **Workaround**: Edit in Serato after export
- **Priority**: Low (not needed for NYE workflow)

#### 2. Single Library Root Assumption
- **Current**: Assumes all tracks under one library root (~/Music)
- **Limitation**: If tracks spread across multiple drives, relative paths may fail
- **Workaround**: Use absolute paths (use_relative_paths=false)
- **Priority**: Low (user's setup uses single library)

#### 3. No Progress Indication for Large Imports
- **Current**: Import is silent until completion
- **Enhancement**: Show progress for playlists with > 100 tracks
- **Priority**: Low (most playlists are < 100 tracks)

#### 4. No Duplicate Detection on Import
- **Current**: Duplicate playlists (by name) cause error
- **Enhancement**: Offer "merge" or "rename" options
- **Priority**: Low (uncommon case)

#### 5. No Playlist Metadata in Exports
- **Current**: Only exports track paths, not playlist description or filters
- **Enhancement**: Include metadata as comments in M3U8
- **Format**:
  ```m3u8
  #EXTINF:123,Artist - Title
  #MM-DESCRIPTION:All dubstep from 2025
  #MM-FILTERS:genre=dubstep AND year>=2025
  /path/to/track.mp3
  ```
- **Priority**: Medium (helps with playlist versioning)

### Phase 6: Playback Integration

#### 1. No Sequential Mode for Library Playback
- **Current**: Sequential mode only works with active playlist
- **Limitation**: Can't play entire library in order
- **Workaround**: Create "All Tracks" smart playlist with no filters
- **Priority**: Low (not needed for DJ workflow)

#### 2. No Custom Sort Order for Sequential Mode
- **Current**: Sequential uses playlist order or filter evaluation order
- **Missing**: Sort by BPM, key, year, rating for DJ sets
- **Enhancement**: Add `playlist sort <field>` command
- **Priority**: Medium (useful for DJ workflow, but can reorder in Serato)

#### 3. Position Tracking Doesn't Handle Playlist Edits
- **Issue**: If track removed from playlist, saved position becomes invalid
- **Current Behavior**: Resume prompt won't appear (track_id not found)
- **Enhancement**: Detect shifts and adjust position
- **Priority**: Low (uncommon edge case)

#### 4. No Visual Progress Through Playlist
- **Current**: Position shown as "5/50"
- **Enhancement**: Show progress bar `[####░░░░░░]`
- **Priority**: Low (nice to have, not critical)

### Phase 7: Sync & Metadata

#### 1. No Real-Time File Watching
- **Current**: Manual sync or startup-only
- **Missing**: Watch filesystem for changes, auto-import on modification
- **Implementation**: Use `watchdog` library
- **Considerations**:
  - Debounce rapid changes (wait 500ms after last change)
  - Handle file locking gracefully (retry with backoff)
  - Run in separate daemon thread
- **Priority**: Medium (Phase 8)

#### 2. No Conflict Resolution UI
- **Current**: Last-write-wins (import overwrites database)
- **Missing**: Detect conflicts (both MM and file changed)
- **Enhancement**:
  - Show diff to user (DB tags vs file tags)
  - Let user choose: keep file, keep DB, or merge
  - Log all conflicts for review
- **Priority**: Low (rare edge case)

#### 3. No Rating Sync
- **Current**: Only tags are synced
- **Missing**: Sync ratings to file metadata
- **Reason**: User decided to skip ratings for now, focus on tags
- **Priority**: Deferred per user request

#### 4. No Progress for Large Exports
- **Current**: Export all 5,000 tracks without progress
- **Enhancement**: Show "Exported 500/5000..." every 1%
- **Priority**: Low (export is fast enough on SSD)

#### 5. Single Metadata Field for All Tags
- **Current**: All tags in one COMMENT field, comma-separated
- **Limitation**: Some players may not parse this format
- **Alternative**: Use multiple COMM frames or custom fields
- **Priority**: Low (works for Serato/MM workflow)

#### 6. No Tag Type Differentiation in Files
- **Current**: User tags and AI tags both written as `mm:tag`
- **Missing**: Distinguish source in file metadata
- **Example**: `mm:user:energetic` vs `mm:ai:buildup`
- **Benefit**: Could re-import with correct source attribution
- **Priority**: Low (database tracks source correctly)

---

## Deferred Items from Phase 7

**Status**: Considered during Phase 7 but deferred as lower priority

1. **File Watching for Real-Time Sync**
   - Use `watchdog` library for filesystem events
   - Background thread watches library_paths
   - Trigger auto-import on file modification event
   - Must debounce (wait for file write to complete)

2. **Conflict Detection UI**
   - Compare database timestamp with file mtime
   - Logic:
     - If both changed since last_synced_at: conflict
     - If only file changed: import from file
     - If only database changed: export to file
   - Prompt: "File and database both changed. Keep [F]ile, [D]atabase, or [M]erge?"

3. **Retry Logic for Locked Files**
   - Windows/Serato often locks files during playback
   - Implement exponential backoff retry
   - Skip file after 3 failed attempts
   - Log locked files for later retry

4. **Export Tag Source Metadata**
   - Write source info to M3U8/crate comments
   - Format: `#MM-TAG:energetic (user)` or `#MM-TAG:buildup (ai)`
   - Enables cross-system source preservation

---

## Recommendations for Future Phases

Based on Phase 7 code review and learnings:

### 1. Comprehensive Test Suite
- **Coverage Areas**:
  - Unit tests for all sync functions
  - Integration tests for import/export workflows
  - Load tests with 10k+ track libraries
  - Concurrent access tests (multiple users/processes)
- **Test Data**:
  - Mock MP3/M4A files with various tag formats
  - Edge cases: empty files, unsupported formats, duplicates
  - Performance: 100+ files for progress reporting
- **Priority**: High for production stability

### 2. File Watching Implementation
- **Approach**: Use `watchdog` library for filesystem events
- **Implementation**:
  ```python
  from watchdog.observers import Observer
  from watchdog.events import FileSystemEventHandler

  class LibraryWatcher(FileSystemEventHandler):
      def on_modified(self, event):
          if event.src_path.endswith(('.mp3', '.m4a')):
              # Debounce and queue for sync
              schedule_sync(event.src_path)
  ```
- **Considerations**:
  - Debounce rapid changes (wait 500ms)
  - Handle Serato file locking on Windows
  - Run in background thread
- **Priority**: Medium (nice quality of life improvement)

### 3. Conflict Detection UI
- **Flow**:
  1. Detect when both DB and file changed since last sync
  2. Show diff: `DB: [energetic, buildup]` vs `File: [energetic, heavy-bass]`
  3. Prompt: Keep file, keep DB, or merge?
  4. Log decision for audit trail
- **Implementation**: Add `detect_conflicts()` function in `sync.py`
- **Priority**: Low (rare edge case, but improves robustness)

### 4. Improved Error Reporting
- **Structured Logging**:
  ```python
  import json
  error_log = {
      'timestamp': time.time(),
      'operation': 'sync_export',
      'file': file_path,
      'error': str(e),
      'traceback': traceback.format_exc()
  }
  with open('errors.jsonl', 'a') as f:
      f.write(json.dumps(error_log) + '\n')
  ```
- **User-Facing Dashboard**:
  - `sync errors` - Show recent error summary
  - `sync report` - Export detailed error report
- **Priority**: Medium (helps debugging production issues)

### 5. Health Checks
- **Startup Validation**:
  - Verify sync integrity (mtime consistency)
  - Check for orphaned temp files (*.tmp)
  - Validate database schema version
  - Auto-repair common issues
- **Implementation**: Add `health_check()` function called on startup
- **Priority**: Medium (prevents data issues)

### 6. Performance Monitoring
- **Metrics to Track**:
  - Sync times per operation (import/export/rescan)
  - Memory usage during batch operations
  - Database query performance
  - File I/O throughput
- **Alerting**: Warn if operations take >5s
- **Optimization**: Profile and optimize hot paths
- **Priority**: Low (current performance is acceptable)

### 7. Security Hardening
- **Path Traversal Prevention**:
  ```python
  def validate_path(file_path, library_root):
      resolved = Path(file_path).resolve()
      if not str(resolved).startswith(str(library_root)):
          raise ValueError("Path outside library root")
  ```
- **Tag Content Sanitization**:
  - Remove control characters from tags
  - Limit tag length (max 100 chars)
  - Validate character encoding
- **Permission Validation**:
  - Check file permissions before writes
  - Handle read-only files gracefully
- **Rate Limiting**:
  - Prevent DOS from rapid sync operations
  - Throttle file operations if needed
- **Priority**: Medium (important for multi-user environments)

---

## Future Enhancements (Out of Scope)

These features were discussed but are beyond the current project scope:

1. **Playlist Reordering UI**
   - Difficult in CLI, consider TUI or web interface
   - May need textual framework or web UI

2. **Playlist Versioning**
   - Track history of playlist changes
   - Git-like diff and rollback

3. **Collaborative Playlists**
   - Share playlists with other Music Minion users
   - Requires cloud sync or P2P

4. **Streaming Service Integration**
   - Spotify, Apple Music, YouTube Music
   - Match local tracks to streaming IDs

5. **Smart Shuffle Algorithms**
   - BPM-matching for seamless transitions
   - Energy flow optimization
   - Key compatibility checking

6. **DJ Set Preparation Tools**
   - Analyze transitions between tracks
   - Suggest optimal track order
   - Export cue points and beatgrids

---

## Command Improvements

### Planned Command Enhancements

1. **`add` Command Without Argument**
   - Current: `add <playlist_name>` - must specify name
   - Enhancement: `add` shows recent playlists, select one
   - UI: Numbered list of recent playlists
   - Priority: Medium

2. **`playlist analyze <name>` Command**
   - Analyze patterns in playlist
   - Suggest smart playlist conversion
   - Show statistics (genres, years, BPM ranges)
   - Priority: Low (Phase 8)

3. **`playlist sort <field>` Command**
   - Sort active playlist by field
   - Options: bpm, key, year, rating, artist, title
   - Useful for DJ set preparation
   - Priority: Medium

4. **`sync watch` Command**
   - Start file watching daemon
   - Monitors library for changes
   - Auto-imports on modification
   - Priority: Medium (Phase 8)

5. **`sync conflicts` Command**
   - Show detected conflicts
   - Allow manual resolution
   - Export conflict report
   - Priority: Low

---

## Technical Debt

### Items to Address

1. **Playlist Rename with Multi-Word Names**
   - Issue: `playlist rename Old Name New Name` splits incorrectly
   - Fix: Use quoted strings or explicit separator
   - Priority: Low

2. **No Track Position Feedback**
   - Issue: `add` says "already in playlist" without position
   - Enhancement: Show "Track already at position 5"
   - Priority: Low

3. **Smart Playlist Filter Evaluation Order**
   - Current: No guaranteed order for smart playlist results
   - Enhancement: Add ORDER BY clause option
   - Priority: Low

4. **Database Index Optimization**
   - Current: Basic indexes on common queries
   - Enhancement: Analyze slow queries, add compound indexes
   - Priority: Low (performance is acceptable)

---

## Testing Priorities

### Critical Tests Needed

1. **Data Loss Scenarios**
   - Tag ownership and removal logic
   - Bidirectional sync with conflicts
   - File corruption recovery

2. **File Operations**
   - Atomic writes work correctly
   - Temp file cleanup on failure
   - Permission handling

3. **Edge Cases**
   - Empty files
   - Unsupported formats
   - Duplicate tags
   - Very long tag values
   - Special characters in tags

4. **Performance at Scale**
   - 10k+ track libraries
   - 1000+ track playlists
   - Rapid successive operations

5. **Concurrent Access**
   - Multiple Music Minion instances
   - External file modifications during sync
   - Database locking behavior

---

## Documentation Needed

### User Documentation

1. **Getting Started Guide**
   - Installation
   - Configuration
   - First-time setup
   - Common workflows

2. **Feature Documentation**
   - Playlist system (manual vs smart)
   - AI natural language parsing
   - Import/Export formats
   - Sync and metadata

3. **Troubleshooting Guide**
   - Common errors and solutions
   - Sync conflict resolution
   - Performance optimization
   - FAQ

4. **Configuration Reference**
   - All config options explained
   - Default values
   - Examples for common setups

### Developer Documentation

1. **Architecture Overview**
   - Module structure and dependencies
   - Database schema
   - Data flow diagrams

2. **API Reference**
   - All public functions
   - Parameters and return types
   - Examples

3. **Contributing Guide**
   - Code style
   - Testing requirements
   - Pull request process

4. **Migration Guide**
   - Schema version history
   - Migration process
   - Backwards compatibility

---

## Priority Summary

### High Priority (Production Blockers)
- None - all critical features are complete

### Medium Priority (Quality of Life)
- File watching for real-time sync
- Conflict detection UI
- Custom sort order for playlists
- Health checks
- Security hardening

### Low Priority (Nice to Have)
- Filter editing UI
- Advanced text matching (regex)
- Progress indicators for large operations
- Visual progress bars
- Comprehensive documentation

### Deferred (Future Consideration)
- Rating sync (user decision)
- Playlist reordering UI (needs TUI/web)
- Streaming service integration
- Collaborative playlists

---

**Last Updated**: 2025-09-29
**Source**: Extracted from docs/playlist-system-plan.md
**Status**: Ready for Phase 8 planning