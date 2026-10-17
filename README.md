# 🎵 Music Minion CLI

> A contextual music curation tool that learns your preferences over time

Music Minion CLI is a smart music player that goes beyond simple ratings. Instead of static 5-star systems, it captures **when** and **why** you like songs, building a temporal understanding of your musical taste that evolves throughout the day, week, and seasons.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform: Linux](https://img.shields.io/badge/platform-linux-lightgrey.svg)](https://www.linux.org/)

## 🔥 Key Features

### 🧠 **Contextual Intelligence**
- **Temporal Patterns**: Track when you love vs. skip songs (morning energy vs. evening chill)
- **Preference Evolution**: See how your relationship with music changes over time
- **Memory Palace**: Link songs to life moments through contextual notes
- **AI Review System**: Conversational tag feedback with learning accumulation
- **Prompt Enhancement**: AI-powered continuous improvement of tagging prompts

### ⭐ **Interactive Rating System**
- **Archive**: Remove from rotation permanently
- **Skip**: Skip without penalty (mood-dependent)
- **Like**: Basic positive rating
- **Love**: Strong positive rating with context capture
- **Note**: Add rich contextual annotations

### 🎧 **DJ-Ready Metadata**
- Musical key detection and display
- BPM (beats per minute) tracking
- Seamless integration with DJ software
- Metadata preservation in file comments

### 🎵 **Smart Playback**
- Cross-platform audio via [MPV](https://mpv.io/)
- Intelligent shuffling based on preferences
- Real-time progress tracking
- Emergency controls (`killall` command)

### 🌐 **Multi-Source Integration**
- **Local Files**: MP3, M4A, FLAC from your filesystem
- **SoundCloud**: Stream liked tracks, sync playlists via OAuth
- **Spotify**: Full library sync with Web Playback SDK (Premium required)
- **OAuth Authentication**: Secure provider login with PKCE
- **Background Syncing**: Real-time progress with thread-safe updates
- **Track Deduplication**: TF-IDF matching across providers (~10ms per track)

### 🎮 **External Control**
- **IPC System**: Background control via Unix socket
- **CLI Commands**: `music-minion skip|love|like|la|nq|ni|add <playlist>`
- **Desktop Notifications**: Track changes and playback events
- **Control Anywhere**: From any terminal, script, or automation

### 🎨 **Advanced Features**
- **Smart Playlists**: Filter-based playlists with AI natural language parsing
- **Track Viewer**: Interactive UI for browsing playlist tracks
- **Playback History**: Track all played songs with timestamps
- **Hot-Reload**: Development mode with instant code reloading (`--dev`)
- **Sync System**: Bidirectional metadata sync (Linux ↔ Windows/Serato)

## 🚀 Quick Start

### Prerequisites
- **Python 3.12+** (check with `python --version`)
- **MPV media player** (for audio playback)
- **UV** package manager (for installation)

### Installation

```bash
# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone <repository-url>
cd music-minion-cli
uv sync

# Install music-minion command
uv pip install -e .

# Initialize configuration
music-minion init
```

### Platform-Specific MPV Installation

```bash
# Ubuntu/Debian
sudo apt install mpv

# Arch Linux
sudo pacman -S mpv

# macOS
brew install mpv

# Windows
winget install mpv
```

### First Run

```bash
# Start interactive mode
music-minion

# Scan your local music library
music-minion> scan

# (Optional) Authenticate with streaming providers
music-minion> library auth soundcloud
music-minion> library auth spotify

# (Optional) Sync provider libraries (runs in background)
music-minion> library sync soundcloud
music-minion> library sync spotify

# Start playing
music-minion> play

# Rate your first song!
music-minion> love
music-minion> note "Perfect morning energy track"

# Control from external terminal (IPC)
music-minion skip
music-minion love
```

## 📖 Usage Guide

### Interactive Commands

Music Minion CLI runs in an interactive shell where you can control playback and rate songs in real-time:

```bash
music-minion> help                    # Show all commands
music-minion> play                    # Play random song
music-minion> play daft punk          # Search and play specific artist
music-minion> status                  # Show current song and progress

# Rating commands (use while song is playing)
music-minion> love                    # Mark as loved ❤️
music-minion> like                    # Mark as liked 👍  
music-minion> skip                    # Skip to next song ⏭️
music-minion> archive                 # Remove permanently 🗑️
music-minion> note "Great drop at 2:15" # Add contextual note 📝

# Playback control
music-minion> pause                   # Pause playback ⏸️
music-minion> resume                  # Resume playback ▶️
music-minion> stop                    # Stop playback ⏹️

# Library management
music-minion> scan                    # Rescan local music library
music-minion> stats                   # Show listening statistics

# Multi-source library commands
music-minion> library active          # Show current active library
music-minion> library active spotify  # Switch to Spotify library
music-minion> library auth soundcloud # Authenticate with SoundCloud
music-minion> library sync spotify    # Sync Spotify library (background)
music-minion> library playlists sync spotify  # Sync Spotify playlists

# Playback history
music-minion> history                 # Show last 50 played tracks
```

### External Control (IPC)

Control Music Minion from any terminal or script:

```bash
# Playback control
music-minion skip                     # Skip to next track

# Rating commands
music-minion love                     # Love current track
music-minion like                     # Like current track

# Playlist shortcuts
music-minion add <playlist>           # Add current track to a playlist
music-minion la                       # Like + add to this month's playlist
music-minion nq                       # Add to "Not Quite"
music-minion ni                       # Add to "Not Interested" and skip
```

Run `music-minion --help` for the full list (web-* controls, locate-opus, sync-radio).

### Temporal Context Capture

Every rating includes automatic context capture:

- **Time**: Hour and day of week
- **Session**: What played before/after
- **Patterns**: How this compares to previous ratings

Example output:
```
❤️  Loved: Daft Punk - Around the World
   Loved on Wednesday at 15:32
   BPM: 123, Key: F# minor
```

### Music Library Setup

Configure library paths in `config.toml` (see Configuration Files below for lookup order):

```toml
[music]
library_paths = ["~/Music", "/media/music"]
supported_formats = [".mp3", ".m4a", ".wav", ".flac"]
scan_recursive = true
```

## ⚙️ Configuration

### Configuration Files

Music Minion stores configuration in:
- **Config**: `config.toml` in the project root (dev), else the current directory, else `~/.config/music-minion/config.toml`
- **Database**: `~/.local/share/music-minion/music_minion.db`
- **Logs**: `~/.local/share/music-minion/logs/`

### Key Settings

```toml
[music]
library_paths = ["~/Music"]          # Directories to scan
supported_formats = [".mp3", ".m4a"] # File types to include
scan_recursive = true                # Include subdirectories

[player]
volume = 50                         # Default volume (0-100)
shuffle_on_start = true            # Start in shuffle mode

[ai]
enabled = false                    # Enable AI note processing
openai_api_key = "your-key-here"   # OpenAI API key (optional)
model = "gpt-4o-mini"             # AI model for analysis

[ui]
show_progress_bar = true          # Show playback progress
use_colors = true                 # Colorful terminal output
history_length = 10               # Recent songs to display

[providers.soundcloud]
# OAuth tokens (auto-populated via `library auth soundcloud`)
access_token = ""
refresh_token = ""

[providers.spotify]
# OAuth tokens (auto-populated via `library auth spotify`)
client_id = "your-client-id"
client_secret = "your-client-secret"
access_token = ""
refresh_token = ""
```

**Note**: Provider OAuth tokens are automatically managed after running `library auth <provider>`. No manual configuration needed.

## 🔧 Technical Architecture

### Project Structure

```
music-minion-cli/
├── src/music_minion/
│   ├── main.py          # Entry point and interactive loop
│   ├── cli.py           # CLI entry point
│   ├── core/            # Core infrastructure (config, database, console)
│   ├── domain/          # Business logic (ai, library, playback, playlists, sync)
│   ├── commands/        # Command handlers (functional)
│   ├── ui/              # User interface (blessed-based)
│   └── utils/           # Utilities (parsers)
├── web/                 # FastAPI backend + Vite/React frontend
├── mobile/              # Expo app
├── shared/              # Shared TS code (web + mobile)
├── docs/                # Documentation (reference/, plans, reports)
├── pyproject.toml       # Project configuration
├── CLAUDE.md           # Development guide
├── ai-learnings.md     # Patterns and best practices
└── README.md           # This file
```

### Core Technologies

- **Audio**:
  - MPV with JSON IPC for local/SoundCloud playback
  - Spotify Web Playback SDK for Spotify Premium streaming
- **Metadata**: Mutagen library for MP3/M4A tag reading/writing
- **Database**: SQLite for ratings, context, temporal data, provider state
- **UI**: blessed for full-screen terminal with functional patterns
  - Three-tier rendering (full/input/partial for flicker-free updates)
  - Immutable state management via dataclasses
- **Logging**: loguru for centralized logging with rotation
- **Config**: Python's built-in tomllib for TOML configuration
- **Providers**:
  - spotipy for Spotify Web API integration
  - OAuth 2.0 + PKCE for secure provider authentication
- **AI**: OpenAI API for intelligent tagging and learning
- **IPC**: Unix sockets for external control
- **Dev Tools**: watchdog for hot-reload during development

### Database Schema

Key tables (v17+):
- **tracks**: File paths, metadata, DJ info (key, BPM)
  - Multi-source: `source` column ('local', 'soundcloud', 'spotify')
  - Provider IDs: `soundcloud_id`, `spotify_id` for linking
- **ratings**: User feedback with timestamps and context
  - Source tracking: `source` column ('user', 'soundcloud', 'spotify')
- **notes**: Rich annotations linked to specific tracks
- **playback_history**: All played songs with timestamps
- **playlists**: Manual and smart playlists
- **provider_state**: OAuth tokens and provider-specific state
- **active_library**: Current active library ('local', 'soundcloud', 'spotify')

## 👨‍💻 Development

### Setup Development Environment

```bash
# Clone repository
git clone <repository-url>
cd music-minion-cli

# Install development dependencies
uv sync --dev

# Install in development mode
uv pip install -e .

# Start with hot-reload for development
music-minion --dev

# Run tests (when available)
pytest

# Check code style
ruff check src/
ruff format src/
```

### Development Resources

- **[CLAUDE.md](CLAUDE.md)** - Comprehensive development guide
- **[ai-learnings.md](ai-learnings.md)** - Patterns and best practices
- **[docs/reference/](docs/reference/)** - Reference docs (Syncthing setup, etc.)

### Code Style Guidelines

- **Functional Programming**: Prefer functions over classes
- **Type Hints**: Required for all public functions
- **Single Responsibility**: Functions ≤20 lines, ≤3 nesting levels
- **Path Handling**: Use `pathlib.Path` over string paths
- **Error Handling**: Graceful degradation for non-critical errors

### Contributing

1. Follow the functional programming approach outlined in `CLAUDE.md`
2. Add type hints to all functions
3. Write docstrings for public functions
4. Test cross-platform compatibility where relevant
5. Update README if adding new features

## 🛠️ Troubleshooting

### Common Issues

**MPV not found**
```bash
# Check if MPV is installed
mpv --version

# Install MPV (see platform-specific instructions above)
```

**No music files found**
```bash
# Check your library paths
music-minion> init
# Edit config.toml (project root or ~/.config/music-minion/)
# Add your music directories to library_paths
```

**Socket connection failed**
```bash
# Kill any hanging MPV processes
music-minion> killall

# Clear leftover socket files
rm /tmp/mpv-socket-*
```

**Database issues**
```bash
# Check database location
ls -la ~/.local/share/music-minion/

# Reinitialize if corrupted
music-minion> init
```

### Debug Logging

Enable detailed logging by setting environment variable:
```bash
export MUSIC_MINION_DEBUG=1
music-minion
```

Logs are written to `~/.local/share/music-minion/logs/`

## 🗺️ Roadmap

### ✅ Completed (Phases 1-7 + Multi-Source)
- ✅ Core playlist infrastructure (manual & smart playlists)
- ✅ AI-powered natural language playlist parsing
- ✅ Import/export (M3U, Serato .crate)
- ✅ Bidirectional metadata sync
- ✅ AI tag review with conversational feedback
- ✅ Prompt enhancement and learning accumulation
- ✅ Hot-reload development mode
- ✅ Track viewer and smart playlist wizard
- ✅ **Multi-source integration** (SoundCloud, Spotify)
- ✅ **OAuth 2.0 + PKCE authentication**
- ✅ **Background library/playlist syncing**
- ✅ **Playback history tracking**
- ✅ **IPC control system** (`music-minion <command>`)
- ✅ **Track deduplication** (TF-IDF matching)
- ✅ **Spotify Web Playback SDK** integration
- ✅ **blessed UI migration** (functional rendering)

### Phase 8: Polish & Testing (Current)
- [ ] File watching for real-time sync
- [ ] Conflict detection UI
- [ ] Comprehensive test suite
- [ ] Performance monitoring
- [ ] Documentation improvements

### Future Vision
- [ ] Web UI for mobile control
- [ ] Global hotkey support (rate from anywhere)
- [ ] USB button controller integration
- [ ] YouTube Music integration
- [ ] Apple Music integration
- [ ] Advanced temporal analytics and visualizations
- [ ] Social sharing of musical discoveries

See [TODOS.md](TODOS.md) for open work.

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- [MPV](https://mpv.io/) for excellent cross-platform audio playback
- [Mutagen](https://github.com/quodlibet/mutagen) for robust metadata handling
- [Rich](https://github.com/Textualize/rich) for beautiful terminal output
- The DJ community for musical key and BPM standards

---

**Music Minion CLI** - Building a smarter relationship with your music, one rating at a time. 🎶