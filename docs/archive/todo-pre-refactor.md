# Music Minion CLI - Development Todo List

## ✅ Completed Tasks

### Core Infrastructure
- ✅ **Create Python project structure with UV package manager**
  - UV project initialized with src/music_minion/ package structure
  - Python 3.12+ environment configured

- ✅ **Set up pyproject.toml with dependencies and console script entry point**
  - Dependencies configured: mutagen, openai, python-dotenv, rich/textual
  - `music-minion` console script entry point working
  - Python 3.12+ requirement enforced

- ✅ **Create basic main.py entry point with simple command parsing**
  - Interactive loop with command routing implemented
  - Clean command parsing with args support
  - Help system with examples

- ✅ **Implement config.py for TOML configuration loading**
  - TOML configuration in ~/.config/music-minion/
  - Default config creation on first run
  - Graceful handling of missing/invalid configs

### Music Library & Metadata
- ✅ **Create library.py for music file scanning (MP3/M4A/WAV)**
  - Functional architecture (no classes, pure functions)
  - Metadata extraction: title, artist, album, genre, year
  - DJ metadata: **key signature and BPM extraction**
  - Search by artist, title, album, key, genre
  - Format support: MP3, M4A, WAV, FLAC

### Database & Persistence
- ✅ **Implement database.py for SQLite operations and schema**
  - Functional architecture with context managers
  - Tables: tracks, ratings, notes, playback_sessions, tags, ai_requests
  - Temporal tracking: hour_of_day, day_of_week
  - Archive management for excluded tracks
  - Rating patterns analysis
  - AI tag management with blacklisting support
  - Token usage tracking and cost analysis

### Player Integration
- ✅ **Create player.py for mpv integration with JSON IPC**
  - Functional architecture with PlayerState NamedTuple
  - Cross-platform socket communication
  - Full control: play, pause, resume, stop, seek
  - Status tracking and progress reporting
  - MPV availability checking with install instructions (Linux/macOS/Windows)

### Core Commands
- ✅ **Implement basic playback commands (play, pause, skip)**
  - `play [query]` - Random or search-based playback
  - `pause` / `resume` - Playback control
  - `skip` - Smart shuffle excluding archived tracks
  - `stop` - Stop playback
  - `status` - Beautiful status display with progress bar

- ✅ **Add rating system commands (archive, like, love, note)**
  - `archive` - Remove from rotation permanently
  - `like` / `love` - Contextual ratings with timestamps
  - `note "text"` - Add notes for future AI processing
  - Temporal context captured (day/time patterns)
  - Archive filtering in shuffle

- ✅ **Implement music-minion init command for setup**
  - Creates config directories
  - Initializes database schema
  - Sets up default configuration

- ✅ **Add basic shuffle functionality through library**
  - Random track selection
  - Excludes archived tracks automatically
  - Avoids repeating current track

### Performance & Database Optimization
- ✅ **Implement library scanning and database population**
  - `scan` command to populate database from filesystem
  - Full library metadata extraction and storage
  - Library statistics and format analysis
  - Progress reporting during scan operations

- ✅ **Add database statistics and analytics commands**
  - `stats` command showing library analytics
  - Rating distribution and temporal patterns
  - Most active hours and days analysis
  - Recent ratings history display

- ✅ **Optimize library loading performance**
  - Database-first loading instead of filesystem scanning
  - Load from database in ~100-500ms vs 5-10 seconds
  - Smart fallback to filesystem scan when database empty
  - File existence validation without full metadata re-read
  - Optimized archived track filtering with SQL queries

## 📋 Remaining Tasks (Immediate Priority)

### State Management
- ⬜ **Add persistent state management for player connection**
  - Save MPV socket path to state file
  - Allow commands to reconnect to existing MPV instance
  - Handle stale state gracefully
  - Clean up on exit
  - Consider daemon mode for future

### User Interface
- ✅ **Create ui.py for terminal display and formatting**
  - Rich/textual based terminal UI
  - Real-time progress updates
  - Recent history with ratings
  - Session statistics
  - Now playing with scrolling text for long titles

### Data Export
- ⬜ **Add metadata writing with mutagen library**
  - Write ratings to file metadata (comment field)
  - DJ-compatible format: "085 - Great buildup, drops at 1:32"
  - Backup original metadata before modification
  - Batch update functionality

### AI Features  
- ✅ **Implement AI integration for note processing**
  - OpenAI Responses API integration with gpt-4o-mini
  - Process track metadata + notes to extract discoverable tags
  - Hybrid API key management (.env files + environment variables)
  - `ai setup <key>` - Configure OpenAI API key
  - `ai analyze` - Manual track analysis with AI tagging
  - `ai test` - Test AI prompts with random tracks and detailed reports
  - `ai usage` - Comprehensive token usage and cost tracking
  - `tag list` - View all track tags (AI + user)
  - `tag remove <tag>` - Blacklist unwanted AI tags
  - Auto-analysis when tracks finish playing (non-intrusive)
  - Graceful error handling and workflow preservation
  - Detailed markdown test reports for prompt iteration

### File Validation & Error Handling
- ⬜ **Handle corrupted/invalid music files gracefully**
  - Add `music-minion validate` command to scan for problematic files:
    - Files too small (< 100KB likely only metadata)
    - Files that can't be read by mutagen (MPEG frame sync errors)
    - Files that mpv can't play
    - Generate report with option to quarantine bad files
  - Auto-skip corrupted files during playback:
    - Detect playback failure immediately after play command
    - Log failure to ~/.local/share/music-minion/playback-errors.log
    - Automatically skip to next track
    - Show brief user message: "⚠ Skipping unplayable file: [filename]"
  - Maintain blacklist of known unplayable files in database
  - Suppress mutagen warnings, use debug logging instead
  - Add --verbose flag to show detailed error messages when needed

### System & Debugging
- ⬜ **Create logging system (error + debug logs)**
  - Dual logging: user-facing errors + detailed debug
  - Log rotation to prevent disk fill
  - Log levels: ERROR, WARNING, INFO, DEBUG
  - Separate log files in ~/.local/share/music-minion/logs/


## 🚀 Future Enhancements (Post-MVP)

### Advanced Analytics
- ⬜ View rating patterns and insights
- ⬜ Export listening history and patterns
- ⬜ Time-based preference reports

### Playlist Management
- ⬜ Create playlists from ratings/patterns
- ⬜ Export playlists to M3U/PLS formats
- ⬜ Smart playlists based on context

### Advanced Player Features
- ⬜ Volume control commands
- ⬜ Seek to position
- ⬜ Repeat modes
- ⬜ Queue management

### Integration Features
- ⬜ Watch mode for library changes
- ⬜ Import ratings from other players
- ⬜ Web UI for remote control
- ⬜ Global hotkey support

---

*Last updated: Current session - Complete AI integration implemented! OpenAI Responses API with smart tagging, comprehensive usage tracking, and iterative testing system.*