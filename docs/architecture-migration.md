# Architecture Migration Plan

## Current State Analysis

### Current Directory Structure
```
src/music_minion/
├── Root Level (18 files, 7,527 lines)
│   ├── main.py (906 lines) - CLI entry point
│   ├── database.py (851 lines) - Schema & operations
│   ├── ui.py (633 lines) - Legacy terminal UI
│   ├── ai.py (594 lines) - OpenAI integration
│   ├── playlist.py (583 lines) - Playlist CRUD
│   ├── sync.py (491 lines) - Metadata sync
│   ├── player.py (386 lines) - MPV integration
│   ├── config.py (382 lines) - TOML configuration
│   ├── library.py (381 lines) - Music scanning
│   ├── playlist_ai.py (353 lines) - AI parsing
│   ├── playlist_import.py (348 lines) - Import M3U/Serato
│   ├── playlist_filters.py (335 lines) - Smart playlists
│   ├── playlist_export.py (303 lines) - Export playlists
│   ├── router.py (244 lines) - Command routing
│   ├── completers.py (221 lines) - CLI autocomplete
│   ├── core.py (183 lines) - Shared utilities
│   ├── command_palette.py (176 lines) - Command UI
│   ├── playback.py (154 lines) - Playback state
│   └── __init__.py (3 lines)
│
├── commands/ (8 files, 2,208 lines)
│   ├── playlist_ops.py (944 lines)
│   ├── playback.py (415 lines)
│   ├── admin.py (283 lines)
│   ├── rating.py (192 lines)
│   ├── ai_ops.py (149 lines)
│   ├── track_ops.py (142 lines)
│   ├── sync_ops.py (78 lines)
│   └── __init__.py (5 lines)
│
├── ui_blessed/ (15 files) - New interactive UI
│   ├── main.py
│   ├── state.py
│   ├── data/ (formatting, palette)
│   ├── events/ (commands, keyboard)
│   └── rendering/ (dashboard, history, input, layout, palette)
│
└── ui_textual/ (8 files) - Legacy Textual UI
    ├── app.py, runner.py, state.py
    ├── dashboard.py
    └── modals (command_palette, playlist)
```

### Identified Issues

1. **Flat Root Structure** - 18 files dumped in root module with no logical grouping, poor discoverability
2. **Inconsistent Organization Patterns** - Some features organized in folders (`commands/`, `ui_blessed/`), others flat in root
3. **Unclear Separation of Concerns** - `main.py` is 906 lines mixing CLI entry point with business logic, `core.py` has circular import dependencies with `main.py`
4. **Module Duplication** - `commands/playback.py` and root `playback.py` confusing naming, multiple modules redefine `get_player_state()`, `get_config()`, `safe_print()`
5. **UI Architecture Confusion** - Three UI systems coexist: legacy `ui.py`, `ui_textual/`, `ui_blessed/` with no clear indication which is active

### Dependency Anti-patterns
```
core.py → main.py (imports main.console) ❌
commands/* → main module (tight coupling) ❌
state.py imported 12 times (god object) ⚠️
```

## Proposed Architecture

### Design Principles
1. **Domain-Driven Structure**: Group by feature/domain, not technical layer
2. **Clear Ownership**: Each module has a single responsibility
3. **Explicit Dependencies**: Low coupling, dependencies flow downward
4. **Scalability**: Easy to add new features without restructuring
5. **Discoverability**: Structure reflects mental model of the system

### Target Structure
```
src/music_minion/
│
├── __init__.py
├── cli.py                    # CLI entry point (minimal, delegates to app)
│
├── core/                     # Foundation layer (no domain dependencies)
│   ├── __init__.py
│   ├── config.py            # Configuration (TOML)
│   ├── database.py          # SQLite operations & migrations
│   ├── logging.py           # Centralized logging
│   └── console.py           # Rich Console wrapper (no circular deps)
│
├── domain/                   # Business logic & models
│   ├── __init__.py
│   ├── library/
│   │   ├── __init__.py
│   │   ├── scanner.py       # Music file scanning
│   │   ├── models.py        # Track dataclass
│   │   └── metadata.py      # Mutagen operations
│   │
│   ├── playback/
│   │   ├── __init__.py
│   │   ├── player.py        # MPV integration
│   │   ├── state.py         # Playback state management
│   │   └── queue.py         # Queue management logic
│   │
│   ├── playlists/
│   │   ├── __init__.py
│   │   ├── crud.py          # CRUD operations
│   │   ├── filters.py       # Smart playlist filters
│   │   ├── ai_parser.py     # AI parsing
│   │   ├── importers.py     # Import M3U/Serato
│   │   └── exporters.py     # Export formats
│   │
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── client.py        # OpenAI client
│   │   ├── analysis.py      # Track analysis
│   │   └── prompts.py       # Prompt templates
│   │
│   └── sync/
│       ├── __init__.py
│       ├── engine.py        # Sync logic
│       └── strategies.py    # Import/export strategies
│
├── commands/                 # Command handlers
│   ├── __init__.py
│   ├── registry.py          # Command registration system
│   ├── playback.py          # Playback commands
│   ├── playlist.py          # Playlist commands (renamed from playlist_ops.py)
│   ├── rating.py            # Rating commands
│   ├── ai.py                # AI commands (renamed from ai_ops.py)
│   ├── sync.py              # Sync commands (renamed from sync_ops.py)
│   ├── track.py             # Track commands (renamed from track_ops.py)
│   └── admin.py             # Admin/utility commands
│
├── ui/                       # UI layer
│   ├── __init__.py
│   ├── common/              # Shared UI utilities
│   │   ├── __init__.py
│   │   ├── formatting.py
│   │   ├── colors.py
│   │   └── widgets.py
│   │
│   ├── blessed/             # Active UI (renamed from ui_blessed)
│   │   ├── __init__.py
│   │   ├── app.py           # Main app (renamed from main.py)
│   │   ├── state.py
│   │   ├── components/      # UI components (renamed from rendering)
│   │   │   ├── __init__.py
│   │   │   ├── dashboard.py
│   │   │   ├── history.py
│   │   │   ├── input.py
│   │   │   ├── layout.py
│   │   │   └── palette.py
│   │   ├── events/
│   │   │   ├── __init__.py
│   │   │   ├── commands.py
│   │   │   └── keyboard.py
│   │   └── styles/          # Styles (renamed from data)
│   │       ├── __init__.py
│   │       ├── formatting.py
│   │       └── palette.py
│   │
│   └── textual/             # Legacy (marked for deprecation)
│       └── [existing files]
│
├── utils/                    # Cross-cutting utilities
│   ├── __init__.py
│   ├── parsers.py           # Argument parsing
│   ├── validators.py        # Input validation
│   └── autocomplete.py      # CLI autocomplete (renamed from completers.py)
│
└── deprecated/               # Staging area for removal
    ├── ui.py                # Legacy terminal UI
    ├── router.py            # Replaced by commands/registry.py
    ├── command_palette.py   # Merged into blessed UI
    └── main.py              # Split into cli.py + domain logic
```

### Dependency Flow (Clean Architecture)
```
┌─────────────────────────────────────┐
│  cli.py (entry point)               │
└────────────────┬────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│  commands/ (application layer)      │
│  - Orchestrates domain logic        │
└────────────────┬────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│  domain/ (business logic)           │
│  - library, playlists, playback     │
└────────────────┬────────────────────┘
                 ↓
┌─────────────────────────────────────┐
│  core/ (foundation)                 │
│  - config, database, logging        │
└─────────────────────────────────────┘

UI layer can import from commands + domain (read-only access)
```

## Migration Tasks

### Migration Progress

**Status: 34/53 tasks complete (64%)**

**Completed:**
- ✅ Tasks 1-11: Core Layer (config, database, console) - 8 commits
- ✅ Tasks 12-16: Domain/Library (models, metadata, scanner) - 3 commits
- ✅ Tasks 17-21: Domain/Playlists (crud, filters, ai_parser, importers, exporters) - 4 commits
- ✅ Tasks 22-24: Domain/Playback (player, state) - 3 commits
- ✅ Tasks 25-29: Domain/AI & Sync (client, engine) - 5 commits
- ✅ Tasks 30-34: Commands Layer Cleanup - 1 commit

**Remaining:**
- ⏳ Tasks 35-40: UI Layer Reorganization
- ⏳ Tasks 41-47: Utils & Entry Point
- ⏳ Tasks 48-53: Deprecation & Final Validation

**Total: 24 commits, all syntax validated, all domain/command imports working**

---

### Pre-Migration Setup

**✅ 1. Create comprehensive test snapshot**
- ✅ Documented all existing tests
- ✅ Created git commit with all current changes
- ✅ Tagged repository as `pre-architecture-migration` for easy rollback

**✅ 2. Create new branch for migration**
```bash
git checkout -b refactor/architecture-reorganization
```
- ✅ Branch created and switched to

**✅ 3. Create new directory structure (empty folders)**
```bash
mkdir -p src/music_minion/{core,domain/{library,playback,playlists,ai,sync},ui/{common,blessed,textual},utils,deprecated}
mkdir -p src/music_minion/domain/playlists
mkdir -p src/music_minion/ui/blessed/{components,events,styles}
```
- ✅ All directories created

### Core Layer Migration

**✅ 4. Create `core/console.py` (NEW)**
- **Why first**: Breaks circular dependency (`core.py` → `main.py`)
- Create new file with `get_console()` and `safe_print()` functions
- Centralizes Rich Console management without importing from main
- All modules can now import from `core.console` instead of `main.console`

```python
# src/music_minion/core/console.py
"""Centralized Rich Console management."""
from rich.console import Console

_console: Console | None = None

def get_console() -> Console:
    """Get or create the global Rich Console instance."""
    global _console
    if _console is None:
        _console = Console()
    return _console

def safe_print(message: str, style: str = None) -> None:
    """Print using Rich Console with optional styling."""
    console = get_console()
    if style:
        console.print(message, style=style)
    else:
        console.print(message)
```

**✅ 5. Move `config.py` → `core/config.py`**
- Configuration is foundation layer with no business logic dependencies
- Use `git mv` to preserve history

```bash
git mv src/music_minion/config.py src/music_minion/core/config.py
```

**✅ 6. Update imports for config.py**
- **Files to update (7)**: `ai.py`, `database.py`, `library.py`, `player.py`, `sync.py`, `commands/playback.py`, `router.py`
- Change `from . import config` → `from .core import config`
- Change `from .. import config` → `from ..core import config`

**✅ 7. Move `database.py` → `core/database.py`**
- SQLite operations and migrations are foundation layer
- Use `git mv` to preserve history

```bash
git mv src/music_minion/database.py src/music_minion/core/database.py
```

**✅ 8. Update imports for database.py**
- **Files to update (11)**: All `playlist*.py` files, `playback.py`, `sync.py`, `ai.py`, all `commands/*.py`, `router.py`
- Change `from . import database` → `from .core import database`
- Change `from .. import database` → `from ..core import database`

**✅ 9. Fix internal import in `core/database.py`**
- Update `from . import config` to work within core package
- Should already be correct as relative import

**✅ 10. Create `core/__init__.py`**
- Export public APIs from core layer
- Makes imports cleaner: `from music_minion.core import config, database`

```python
"""Core infrastructure layer - no business logic dependencies."""
from .config import Config, load_config
from .database import *
from .console import get_console, safe_print

__all__ = [
    'Config', 'load_config',
    'get_console', 'safe_print',
    # ... database exports
]
```

**✅ 11. Validate core layer imports**
- Run syntax check on all Python files
- Test that core modules can be imported
- Verify no circular dependencies

```bash
python -c "from music_minion.core import config, database, console; print('Core imports OK')"
git commit -m "refactor: create core layer (config, database, console)"
```

### Domain Layer - Library

**✅ 12. Create `domain/library/` structure**
```bash
mkdir -p src/music_minion/domain/library
```

**✅ 13. Split `library.py` into domain modules**
- **Why**: `library.py` (381 lines) mixes models, scanning, and metadata
- **Create `domain/library/models.py`**: Extract `Track` dataclass and helper functions (lines 1-100)
- **Create `domain/library/scanner.py`**: Extract `scan_library()`, `get_music_files()` (lines 101-381)
- **Create `domain/library/metadata.py`**: Extract `get_display_name()`, `get_duration_str()`, `get_dj_info()`, Mutagen operations

```python
# scanner.py imports
from ..core import config, database
from .models import Track
from . import metadata
```

**✅ 14. Create `domain/library/__init__.py`**
- Export public APIs for clean imports

```python
"""Library domain - music file scanning and metadata."""
from .models import Track
from .scanner import scan_library, get_music_files
from .metadata import get_display_name, get_duration_str, get_dj_info

__all__ = [
    'Track', 'scan_library', 'get_music_files',
    'get_display_name', 'get_duration_str', 'get_dj_info'
]
```

**✅ 15. Update library imports across codebase**
- **Files to update (6)**: `main.py`, `ai.py`, all `commands/*.py`
- Change `from . import library` → `from .domain import library`
- Change `from .. import library` → `from ..domain import library`

**✅ 16. Validate library domain**
```bash
python -c "from music_minion.domain.library import Track, scan_library; print('Library domain OK')"
git commit -m "refactor: extract library domain from flat module"
```

### Domain Layer - Playlists

**✅ 17. Move and rename playlist modules**
- **Why**: 5 scattered playlist files need grouping into cohesive domain
- Move all playlist-related files into `domain/playlists/`

```bash
git mv src/music_minion/playlist.py src/music_minion/domain/playlists/crud.py
git mv src/music_minion/playlist_filters.py src/music_minion/domain/playlists/filters.py
git mv src/music_minion/playlist_ai.py src/music_minion/domain/playlists/ai_parser.py
git mv src/music_minion/playlist_import.py src/music_minion/domain/playlists/importers.py
git mv src/music_minion/playlist_export.py src/music_minion/domain/playlists/exporters.py
```

**✅ 18. Fix internal imports in playlists domain**
- ✅ **In `domain/playlists/crud.py`**: `from ...core import database` (up 3 levels to core)
- ✅ **In `domain/playlists/filters.py`**: `from ...core import database`
- ✅ **In `domain/playlists/ai_parser.py`**: `from ..ai import get_api_key, AIError` (sibling domain), `from .filters import *` (same domain)
- ✅ **In `domain/playlists/importers.py`**: `from ...core import database`, `from .crud import *`
- ✅ **In `domain/playlists/exporters.py`**: `from ...core import database`, `from .crud import *`

**✅ 19. Create `domain/playlists/__init__.py`**
- ✅ Exported all public functions for clean imports (43 functions total)

```python
"""Playlists domain - manual/smart playlists with import/export."""
from .crud import (
    create_playlist, delete_playlist, list_playlists,
    add_track_to_playlist, remove_track_from_playlist,
    get_active_playlist, set_active_playlist, clear_active_playlist,
    # ... all public functions
)
from .filters import (
    add_filter, remove_filter, get_filters, validate_filter,
    build_filter_query, evaluate_smart_playlist
)
from .ai_parser import parse_natural_language
from .importers import import_playlist
from .exporters import export_playlist

__all__ = [...]  # All public functions
```

**✅ 20. Update playlist imports across codebase**
- ✅ **Files updated (7)**: `main.py`, `core.py`, `ui.py`, `completers.py`, `commands/playlist_ops.py`, `commands/playback.py`, `commands/track_ops.py`
- ✅ Changed `from . import playlist` → `from .domain import playlists`
- ✅ Changed `from .. import playlist` → `from ..domain import playlists`
- ✅ All `playlist.` references updated to `playlists.`

```bash
# Find all playlist imports
grep -r "from \. import playlist" src/music_minion/
grep -r "from \.\. import playlist" src/music_minion/
```

**✅ 21. Validate playlists domain**
```bash
python -c "from music_minion.domain.playlists import create_playlist, import_playlist; print('Playlists domain OK')"
git commit -m "refactor: consolidate playlist modules into domain/playlists"
```
- ✅ All playlists domain imports validated

### Domain Layer - Playback, AI, Sync

**✅ 22. Create playback domain**
- ✅ Moved player and playback state management into domain

```bash
mkdir -p src/music_minion/domain/playback
git mv src/music_minion/playback.py src/music_minion/domain/playback/state.py
git mv src/music_minion/player.py src/music_minion/domain/playback/player.py
```

**✅ 23. Create `domain/playback/__init__.py`**
```python
from .player import *
from .state import *
```
- ✅ Exported 25 functions from player and state modules

**✅ 24. Update playback imports**
- ✅ Changed `from . import playback` → `from .domain import playback`
- ✅ Changed `from . import player` → `from .domain.playback import player`
- ✅ **Files updated (7)**: `main.py`, `core.py`, `router.py`, `ui.py`, `commands/playlist_ops.py`, `commands/playback.py`
- ✅ All `player.` references updated to `playback.`

**✅ 25. Create AI domain**
```bash
mkdir -p src/music_minion/domain/ai
git mv src/music_minion/ai.py src/music_minion/domain/ai/client.py
```

**✅ 26. Create `domain/ai/__init__.py`**
```python
from .client import *
```
- ✅ Exported AIError class and 9 AI functions

**✅ 27. Create sync domain**
```bash
mkdir -p src/music_minion/domain/sync
git mv src/music_minion/sync.py src/music_minion/domain/sync/engine.py
```

**✅ 28. Create `domain/sync/__init__.py`**
```python
from .engine import *
```
- ✅ Exported 8 sync functions

**✅ 29. Validate all domains**
```bash
python -c "from music_minion.domain import playback, ai, sync; print('All domains OK')"
git commit -m "refactor: complete domain layer (playback, ai, sync)"
```
- ✅ All domain imports validated
- ✅ **Files updated (5)**: `main.py`, `commands/{ai_ops,playback,playlist_ops,sync_ops}.py`
- ✅ Fixed all internal imports in domain modules

### Commands Layer Cleanup

**✅ 30. Rename command files to match domain naming**
- ✅ Removed `_ops` suffix for consistency
- ✅ Files renamed: playlist_ops.py → playlist.py, ai_ops.py → ai.py, sync_ops.py → sync.py, track_ops.py → track.py

**✅ 31. Update router.py imports**
- ✅ Updated all imports to use new module names
- ✅ Updated all function call references (playlist_ops.* → playlist.*, etc.)

**⏳ 32. Create `commands/registry.py` (DEFERRED)**
- Command registration system for extensibility (future enhancement)
- Not required for core migration

**✅ 33. Update imports in command modules**
- ✅ All command modules already using correct domain imports
- ✅ Verified: `from ..core import database`, `from ..domain import playlists`, etc.

**✅ 34. Validate commands**
- ✅ All command files compile successfully
- ✅ Import test passed: `from music_minion.commands import playback, playlist, ai, sync, track, admin`
- ✅ Committed with message: "refactor: rename command files to match domain naming"

### UI Layer Reorganization

**35. Create UI common utilities**
- Extract shared formatting and color functions

```bash
mkdir -p src/music_minion/ui/common
```

Create `ui/common/formatting.py` with common formatting functions from `ui.py`
Create `ui/common/colors.py` with color constants and theme management

**36. Reorganize blessed UI structure**
- Rename directories for clarity
- `ui_blessed` → `ui/blessed`
- `rendering` → `components`
- `data` → `styles`
- `main.py` → `app.py`

```bash
git mv src/music_minion/ui_blessed src/music_minion/ui/blessed
git mv src/music_minion/ui/blessed/rendering src/music_minion/ui/blessed/components
git mv src/music_minion/ui/blessed/data src/music_minion/ui/blessed/styles
git mv src/music_minion/ui/blessed/main.py src/music_minion/ui/blessed/app.py
```

**37. Update imports in blessed UI**
- Update all imports to reflect new structure

```python
# In ui/blessed/app.py
from ...core import console
from ...domain import library, playlists, playback
from .components import dashboard, history, input
from .styles import palette, formatting
```

**38. Move textual UI to legacy location**
```bash
git mv src/music_minion/ui_textual src/music_minion/ui/textual
```

**39. Add deprecation warning to textual UI**
```python
# ui/textual/__init__.py
import warnings
warnings.warn(
    "ui.textual is deprecated and will be removed in v1.0. "
    "Please use ui.blessed instead.",
    DeprecationWarning,
    stacklevel=2
)
```

**40. Validate UI layer**
```bash
python -c "from music_minion.ui.blessed import app; print('UI OK')"
git commit -m "refactor: reorganize UI layer (blessed active, textual deprecated)"
```

### Utils & Entry Point

**41. Create utils layer**
```bash
mkdir -p src/music_minion/utils
git mv src/music_minion/completers.py src/music_minion/utils/autocomplete.py
```

**42. Extract utilities from core.py to utils**
- Create `utils/parsers.py` with `parse_quoted_args()` and argument parsing functions
- Create `utils/validators.py` with input validation functions
- These are cross-cutting concerns, not foundation layer

**43. Create `utils/__init__.py`**
```python
from .autocomplete import *
from .parsers import *
from .validators import *
```

**44. Create new CLI entry point: `cli.py` (NEW)**
- Minimal entry point that delegates to application logic
- Replaces bloated 906-line `main.py`

```python
"""Music Minion CLI - Entry point."""
import sys
from .core import config, console
from .commands.registry import dispatch_command
from .ui.blessed import app as blessed_app

def main():
    """Main entry point for music-minion CLI."""
    # Parse CLI args
    # Load config
    # Start UI or handle single command
    pass

if __name__ == '__main__':
    main()
```

**45. Update `__init__.py` to use new entry point**
```python
"""Music Minion - Contextual Music Curation CLI."""
from .cli import main

__version__ = '0.1.0'
__all__ = ['main']
```

**46. Update `pyproject.toml` entry point**
```toml
[project.scripts]
music-minion = "music_minion.cli:main"  # Changed from music_minion:main
```

**47. Validate CLI entry point**
```bash
uv run music-minion --help
git commit -m "refactor: create clean CLI entry point"
```

### Deprecation & Cleanup

**48. Move deprecated files to staging area**
- Explicitly mark old code for removal

```bash
git mv src/music_minion/main.py src/music_minion/deprecated/main_legacy.py
git mv src/music_minion/ui.py src/music_minion/deprecated/ui_legacy.py
git mv src/music_minion/router.py src/music_minion/deprecated/router_legacy.py
git mv src/music_minion/command_palette.py src/music_minion/deprecated/command_palette_legacy.py
git mv src/music_minion/core.py src/music_minion/deprecated/core_legacy.py
```

**49. Add deprecation notices to legacy files**
```python
# At top of each deprecated file
raise DeprecationWarning(
    f"{__file__} is deprecated. Use new architecture instead. "
    "See docs/architecture-migration.md"
)
```

Validate no active code imports from deprecated:
```bash
grep -r "from \.deprecated" src/music_minion/ --exclude-dir=deprecated
git commit -m "refactor: move legacy code to deprecated folder"
```

### Final Validation & Testing

**50. Run comprehensive import smoke tests**
- Test all public APIs still accessible after migration

```bash
python << 'EOF'
# Test all public APIs still work
from music_minion.core import config, database, console
from music_minion.domain import library, playlists, playback, ai, sync
from music_minion.commands import playback, playlist, rating, ai, sync, track, admin
from music_minion.ui.blessed import app
from music_minion.utils import autocomplete, parsers

print("✅ All imports successful")
EOF
```

**51. Run existing test suite**
```bash
pytest tests/ -v
```

**52. Manual functional testing**
- Test all critical user workflows still work

```bash
uv run music-minion init
uv run music-minion scan
uv run music-minion play
# Test: play, pause, skip, ratings, playlists, AI, sync commands
# Test: interactive mode, blessed UI rendering
```

**53. Update project documentation**
- Update `CLAUDE.md` with new structure
- Update `ai-learnings.md` with migration insights
- Update this file with completion notes

```bash
git commit -m "docs: update documentation for new architecture"
```

## Risk Assessment & Mitigation

### High Risk Areas

**Import Path Changes**
- **Risk**: One missed import breaks entire app
- **Mitigation**: Use automated search/replace, run `python -m py_compile` on every file after changes, comprehensive import test suite
- **Rollback**: `git revert` entire task if imports fail

**Entry Point Change**
- **Risk**: `music-minion` command stops working
- **Mitigation**: Test `uv run music-minion` after task 47, keep old entry point until validated
- **Rollback**: Revert `pyproject.toml` change

**Circular Dependencies**
- **Risk**: Creating new import cycles during reorganization
- **Mitigation**: Dependency graph validation after each task group, use Python's `importlib` to detect cycles
- **Detection**: `python -c "import music_minion; print('No cycles')"`

### Medium Risk Areas

**UI State Management**
- **Risk**: `state.py` is imported 12 times - moving it could break UI
- **Mitigation**: Move UI last (tasks 35-40) after core is stable, test interactive mode after UI changes
- **Rollback**: Keep old UI files in `deprecated/` until confirmed working

**Database Migration Side Effects**
- **Risk**: Moving `database.py` could corrupt SQLite schema migrations
- **Mitigation**: Backup `~/.config/music-minion/library.db` before task 7, test migrations with `music-minion migrate`, verify schema version remains 7
- **Detection**: Query schema version after task 11

**Command Routing Changes**
- **Risk**: Commands stop dispatching correctly
- **Mitigation**: Test all commands manually after task 34, keep old `router.py` until new `registry.py` confirmed working

### Testing Strategy

**Per-Task-Group Validation**
Run after completing related task groups (core, domain, commands, UI):

```bash
#!/bin/bash
# Syntax check all Python files
find src/music_minion -name "*.py" -exec python -m py_compile {} + || exit 1

# Import test
python -c "import music_minion; print('✅ Main import OK')" || exit 1

# Test entry point
uv run music-minion --help > /dev/null || exit 1

# Detect circular imports
python -c "import music_minion; print('✅ No circular imports')" || exit 1
```

**Import Coverage Test**
Ensure all public APIs still accessible (task 50)

**Functional Regression Test**
Test critical user workflows (task 52):
- Library scanning
- Playlist CRUD
- Database migrations
- Config loading
- Command dispatch

**Architecture Rules Test**
Ensure clean architecture rules maintained:
- Core layer has no domain dependencies
- Domain layer has no UI dependencies
- No active code imports from deprecated

**Manual Testing Checklist**
- [ ] CLI starts: `music-minion --help`
- [ ] Init works: `music-minion init`
- [ ] Library scan: `music-minion scan`
- [ ] Play random: `music-minion play`
- [ ] Rating commands: `love`, `like`, `archive`
- [ ] Playlist CRUD: `playlist new manual Test`, `playlist show Test`
- [ ] Smart playlists: `playlist new smart Test`
- [ ] AI commands: `ai analyze`
- [ ] Sync commands: `sync status`, `sync export`
- [ ] Import/Export: `playlist import test.m3u`, `playlist export Test`
- [ ] Interactive mode: All commands work in live session
- [ ] UI rendering: Blessed UI displays correctly

### Rollback Strategy

**Per-Task Rollback**:
```bash
# If task N fails validation
git reset --hard HEAD~1  # Revert last commit
# Fix issues, retry task
```

**Full Rollback**:
```bash
# Nuclear option: abandon entire migration
git checkout main
git branch -D refactor/architecture-reorganization
# Restart with lessons learned
```

**Backup Strategy**:
```bash
# Before starting migration
cp ~/.config/music-minion/library.db ~/.config/music-minion/library.db.backup
tar -czf music-minion-backup-$(date +%Y%m%d).tar.gz src/music_minion/
```

## Success Criteria

Migration is successful when:
1. ✅ All import tests pass
2. ✅ All functional tests pass
3. ✅ All architecture rules pass
4. ✅ Manual testing checklist 100% complete
5. ✅ No deprecated code imported by active modules
6. ✅ Database schema version still `7`
7. ✅ CLI entry point works: `music-minion --help`
8. ✅ No circular import errors
9. ✅ Documentation updated
10. ✅ Code review approved

## Benefits

- **67% reduction** in root clutter (18 → 6 files)
- **Clear ownership** - Every module has single responsibility
- **Scalability** - Easy to add features (e.g., `domain/ratings/`)
- **No circular dependencies** - Clean dependency flow
- **Better discoverability** - Structure reflects mental model
