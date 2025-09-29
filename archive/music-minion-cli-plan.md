# Music Minion CLI - Project Plan

## Project Overview
Build a CLI music player (`music-minion`) focused on contextual music curation through real-time feedback and learning user preferences over time.

## Implementation Guidelines

### Architecture Principles
- **Functional over Classes**: Use functions and modules, avoid complex class hierarchies
- **Single Responsibility**: Each function does one thing well (≤20 lines, ≤3 nesting levels)
- **Simple & Expandable**: Build MVP first, design for easy feature addition later
- **Fail Fast**: Critical errors (missing mpv, no music) should exit with clear messages
- **Graceful Degradation**: Non-critical errors (AI failures, corrupted files) should log and continue

### Python CLI Best Practices
- **Entry Point**: Use `console_scripts` in setup.py/pyproject.toml for `music-minion` command
- **Command Parsing**: Start simple with input().split(), can upgrade to Click/Typer later  
- **Configuration**: Use TOML files in `~/.config/music-minion/`, load with tomllib
- **Logging**: Two levels - user-facing errors and detailed debug logs
- **Cross-Platform**: Use pathlib for paths, handle platform differences in mpv socket paths
- **Dependencies**: Keep minimal - mutagen (metadata), openai (optional), rich/textual (UI)

### Project Structure
```
music-minion/
├── src/music_minion/
│   ├── __init__.py
│   ├── main.py          # Entry point and interactive loop
│   ├── player.py        # mpv integration and control
│   ├── library.py       # Music scanning and metadata
│   ├── database.py      # SQLite operations
│   ├── ai.py           # OpenAI integration
│   ├── config.py       # Configuration loading
│   └── ui.py           # Terminal display and formatting
├── pyproject.toml
└── README.md
```

### Code Style
- Use type hints for function parameters and returns
- Prefer pathlib.Path over string paths  
- Use context managers for file/database operations
- Keep business logic separate from UI code
- Write docstrings for public functions

### File Organization
- **Single Purpose Files**: Each module should contain only related functions
- **Utility Functions**: Create `utils/` folder for reusable code (formatting, validation, etc.)
- **Avoid Duplication**: If code appears in multiple places, extract to shared utility
- **Clear Dependencies**: Files should import what they need, avoid circular imports

## Current Tasks (MVP)

### Core Architecture Setup
- Create Python project structure with `music-minion` package using UV
- Set up `music-minion` command with `music-minion init` for setup/configuration
- Auto-install mpv dependency during initialization  
- Implement basic music library scanning for configurable paths (MP3/M4A/WAV focus)
- Create SQLite database for tracking ratings, context, and notes
- Set up logging system (error log + detailed debug log)

### Basic Playback Integration  
- Integrate with mpv (cross-platform, JSON IPC control) for actual audio playback
- Implement basic shuffle functionality through entire library
- Create simple terminal interface showing current song and progress

### Rating System & AI Integration
- Implement interactive commands: `archive`, `skip`, `like`, `love`, `note "text"`
- Store ratings with timestamp and context (time of day, day of week)
- AI note processing (GPT-4o-mini): auto-process after song ends (unless archived)
- Commands: `ai setup <key>`, `ai analyze library`, `ai process batch`
- Preserve existing tags on AI failures, graceful error handling
- Basic metadata writing to files using mutagen library

### Terminal UI (Simple TUI)
- Current song display with progress bar
- Show DJ metadata: year, genre, key, BPM, existing notes
- AI-extracted tags when available
- Recent history (last 5-10 songs with ratings)
- Basic session stats (songs rated, time played)

## Future Features (Post-MVP)

### Enhanced Context Tracking
- Weather integration for mood correlation
- Activity tagging during rating
- Pattern recognition (genre preferences by time/day)
- Smart playlist generation based on historical patterns

### Advanced Rating & Curation
- DJ-style metadata (0-100 rating in comment field)
- Memory/note system linked to songs
- Rediscovery mode for old/unplayed music
- Archive management and recovery

### Control & Integration
- Web UI for mobile control (localhost server)
- Background daemon for global hotkey support  
- USB button controller integration
- Existing player integration (playerctl/AppleScript/Windows Media Control)
- Spotify/streaming service integration

### Analytics & Visualization
- Mood drift tracking over time
- Music taste evolution graphs
- Context-aware recommendations
- Export capabilities for DJ software

### User Experience
- Web UI for mobile control
- Playlist export to various formats
- Social features (share discoveries)
- Multiple music library support

## Technical Stack
- **Language:** Python 3.12+
- **Environment:** UV for dependency and environment management
- **Audio:** mpv with JSON IPC (cross-platform)
- **Metadata:** mutagen library for MP3/M4A
- **Database:** SQLite for local storage
- **UI:** rich/textual for terminal interface
- **Deployment:** setuptools with console scripts

---

## Detailed Notes from Development Session

### Original Inspiration & Context
Kevin has been thinking about building a better way to rate his local music collection. The idea centers around a USB button controller with 3+ buttons:
- **Never** - Archive the song (remove from rotation)
- **Not Now** - Skip but don't penalize (mood-dependent)
- **Yes** - Like/Love the song

The core insight is that music preference is highly contextual - a song might always get "not now" at 10am but "love" at 4pm. Static ratings miss this temporal dimension.

### Evolution from Static Ratings to Contextual Curation
Instead of simple 1-5 star ratings, Music Minion tracks:
- **When** you like songs (time of day, day of week)
- **Context** around decisions (what played before, session mood)
- **Preference drift** over time (how your relationship with songs changes)
- **Memory association** through notes and tagging

### Architecture Decisions Made

#### Music Player Integration
**Challenge:** Building a music player from scratch is complex.
**Solution:** Integrate with MPD (Music Player Daemon)
- Runs as background service
- Controllable via CLI from anywhere
- Handles audio complexity while we focus on curation logic
- Python integration via `python-mpd2`

#### Control While in Other Applications
**Hybrid Approach Decided:**
```
USB Buttons → System Hotkeys (F13-F15) → Vibe Daemon → MPD
Terminal Commands (mm love) → Vibe Daemon → MPD
Web UI (future) → Vibe Daemon → MPD
```

This allows rating from anywhere without needing the terminal focused.

#### Metadata Strategy
**Dual approach for DJ compatibility:**
- Write actual ratings to file metadata using mutagen
- Store rich context data in separate SQLite database
- Format: "085 - Great buildup, drops at 1:32" in comment field

### User Library Profile
- **Primary:** MP3 (4,766 files) 
- **Secondary:** M4A (368 files)
- **Location:** `~/Music`
- **Platform:** Linux (start here, expand later)

### Terminal Interface Vision
```
╭─ MUSIC MINION ─ Session: 2h 34m ─ Rated: 23 songs ────────╮
│                                                          │
│  🎵  Daft Punk - Around the World                        │
│  ▓▓▓▓▓▓▓▓▓░░░░░░░░ 2:34 / 3:37                          │
│                                                          │
│  [X] Archive  [S] Skip  [L] Like  [Shift+L] LOVE  [N]   │
│                                                          │
│  ── Recent History ──                                    │
│  🟢 Random Access Memories - Daft Punk                  │
│  ⚪ Blue Monday - New Order                              │
│  🔴 Never Gonna Give You Up - Rick Astley               │
│                                                          │
│  ── Context Insights ──                                 │
│  You typically LOVE this artist at 3pm on weekdays     │
╰──────────────────────────────────────────────────────────╯
```

### Command Structure
- **Primary:** `music-minion` (users can create alias to `mm` if desired)
- **Package:** `music-minion` 
- **Interactive mode:** `music-minion` (opens TUI with commands like `play`, `love`, `skip`, `note "text"`)

### Development Philosophy
- **Simplicity First:** MVP before features
- **Context-Aware:** Time and patterns are first-class data
- **Local Control:** Works offline, user owns data
- **Speed Optimized:** Rating commands should be instant
- **Linux First:** Expand to other platforms later

### Key Innovation Points
1. **Temporal Intelligence:** Understanding that music preference changes throughout day/week/season
2. **Memory Palace Concept:** Linking songs to life moments and emotions
3. **Curation vs Consumption:** Focus on building relationship with music, not just playing it
4. **Context Preservation:** Capturing the "why" behind musical choices
5. **Evolution Tracking:** How taste changes over time

### Potential Challenges Identified
- MPD setup complexity for non-technical users
- Global hotkey permissions on different systems
- USB controller mapping across platforms
- Performance with large music libraries
- Metadata corruption risk when writing to files

### Future Integration Possibilities
- **Spotify:** Extend rating system to streaming
- **DJ Software:** Export curated metadata
- **Social:** Share musical discoveries
- **Analytics:** Mood and productivity correlation
- **Health:** Integration with sleep/exercise patterns

### Project Name Heritage
"Music Minion" - Kevin has worked on various versions of this concept and consistently held this name. Represents the idea of a helpful assistant that learns and serves your musical needs.

### Success Metrics for MVP
- Can scan and play local music library
- Rating system captures temporal preferences
- Terminal UI provides immediate feedback
- Commands work from anywhere in system
- Data persists and builds user profile over time

This project represents Kevin's deep understanding of personal productivity tools and his ability to identify gaps in existing solutions. The contextual intelligence concept shows systems thinking beyond simple feature implementation.