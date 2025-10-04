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

### 🎨 **Advanced Features**
- **Smart Playlists**: Filter-based playlists with AI natural language parsing
- **Track Viewer**: Interactive UI for browsing playlist tracks
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

# Scan your music library
music-minion> scan

# Start playing
music-minion> play

# Rate your first song!
music-minion> love
music-minion> note "Perfect morning energy track"
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
music-minion> scan                    # Rescan music library
music-minion> stats                   # Show listening statistics
```

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

Configure library paths in `~/.config/music-minion/config.toml`:

```toml
[music]
library_paths = ["~/Music", "/media/music"]
supported_formats = [".mp3", ".m4a", ".wav", ".flac"]
scan_recursive = true
```

## ⚙️ Configuration

### Configuration Files

Music Minion stores configuration in:
- **Config**: `~/.config/music-minion/config.toml`
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
```

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
│   └── utils/           # Utilities (parsers, autocomplete)
├── docs/                # Documentation
│   ├── ai-tag-review-system.md
│   ├── hot-reload-usage.md
│   ├── playlist-system-plan.md
│   └── incomplete-items.md
├── pyproject.toml       # Project configuration
├── CLAUDE.md           # Development guide
├── ai-learnings.md     # Patterns and best practices
└── README.md           # This file
```

### Core Technologies

- **Audio**: MPV with JSON IPC for cross-platform playback
- **Metadata**: Mutagen library for MP3/M4A tag reading/writing
- **Database**: SQLite for ratings, context, and temporal data
- **UI**: blessed for full-screen terminal interface with functional patterns
- **Config**: Python's built-in tomllib for TOML configuration
- **AI**: OpenAI API for intelligent tagging and learning
- **Dev Tools**: watchdog for hot-reload during development

### Database Schema

Key tables:
- **tracks**: File paths, metadata, DJ info (key, BPM)
- **ratings**: User feedback with timestamps and context
- **notes**: Rich annotations linked to specific tracks
- **playback_sessions**: Listening history and session data

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
- **[docs/hot-reload-usage.md](docs/hot-reload-usage.md)** - Hot-reload development mode
- **[docs/ai-tag-review-system.md](docs/ai-tag-review-system.md)** - AI review system
- **[docs/playlist-system-plan.md](docs/playlist-system-plan.md)** - Implementation history

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
# Edit ~/.config/music-minion/config.toml
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

### ✅ Completed (Phases 1-7)
- ✅ Core playlist infrastructure (manual & smart playlists)
- ✅ AI-powered natural language playlist parsing
- ✅ Import/export (M3U, Serato .crate)
- ✅ Bidirectional metadata sync
- ✅ AI tag review with conversational feedback
- ✅ Prompt enhancement and learning accumulation
- ✅ Hot-reload development mode
- ✅ Track viewer and smart playlist wizard

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
- [ ] Spotify/streaming service integration
- [ ] Advanced temporal analytics and visualizations
- [ ] Social sharing of musical discoveries

See [docs/incomplete-items.md](docs/incomplete-items.md) for detailed roadmap.

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- [MPV](https://mpv.io/) for excellent cross-platform audio playback
- [Mutagen](https://github.com/quodlibet/mutagen) for robust metadata handling
- [Rich](https://github.com/Textualize/rich) for beautiful terminal output
- The DJ community for musical key and BPM standards

---

**Music Minion CLI** - Building a smarter relationship with your music, one rating at a time. 🎶