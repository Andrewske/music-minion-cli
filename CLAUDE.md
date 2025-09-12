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

### Planned Project Structure
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

## Development Setup & Commands

### Environment Management
- Use **UV** for dependency and environment management
- Python 3.12+ required

### Key Dependencies
- **mutagen**: MP3/M4A metadata handling
- **openai**: AI integration (optional)
- **rich/textual**: Terminal UI
- **pathlib**: Cross-platform path handling
- **tomllib**: TOML configuration loading

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

### Context Tracking
- Store ratings with timestamp and context (time of day, day of week)
- Track preference patterns and evolution over time
- Mood correlation and session statistics

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

## Testing & Quality
- Write tests regularly with pytest
- Handle cross-platform differences in mpv socket paths
- Validate metadata operations don't corrupt files
- Test graceful degradation when external services fail

## Future Architecture Considerations
- Global hotkey support through background daemon
- Web UI for mobile control (localhost server)  
- USB button controller integration
- Integration with existing players (playerctl/AppleScript)
- Spotify/streaming service integration