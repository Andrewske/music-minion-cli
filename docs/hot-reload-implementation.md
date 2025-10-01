# Hot Reload Implementation Plan

## Overview
Enable hot-reloading of Python modules during development without restarting the Music Minion CLI application. This allows developers to modify code and see changes immediately by reloading affected modules while preserving application state.

## Desired Behavior

### User Experience
- Start Music Minion with `music-minion --dev` flag to enable hot-reload mode
- Edit any Python file in `src/music_minion/`
- Save the file
- Application automatically detects the change and reloads the affected module
- See immediate feedback: "Reloaded: playlist.py"
- Continue using the app with updated code - no restart needed
- Critical state preserved: current track, player connection, database, active playlist

### What Gets Reloaded
- Command handlers (playlist, sync, playback commands)
- Business logic (filters, AI parsing, import/export)
- UI formatting and display functions
- Helper utilities

### What Doesn't Get Reloaded (Preserved State)
- MPV player connection and socket
- Database connection
- Current track and playback position
- Active playlist selection
- Configuration object
- Music library list

## Implementation Approach

### 1. Dependencies
Add to `pyproject.toml` dev dependencies:
```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "ruff>=0.1.0",
    "watchdog>=3.0.0",  # File system event monitoring
]
```

### 2. File Watcher Setup

**Module**: `src/music_minion/dev_reload.py` (new file)

Create a background thread that:
- Uses `watchdog.observers.Observer` to monitor `src/music_minion/` directory
- Filters events to only `.py` file modifications (ignore `.pyc`, `__pycache__`)
- Debounces rapid successive saves (wait 100ms after last change)
- Triggers reload callback when stable change detected

**Key Classes**:
- `FileChangeHandler(FileSystemEventHandler)` - Handles file modification events
- `setup_file_watcher(callback)` - Initializes observer and returns it
- `stop_file_watcher(observer)` - Cleanup on exit

### 3. Module Reloading Logic

**Module**: Add to `src/music_minion/dev_reload.py`

Implement smart module reloading:

```python
import importlib
import sys

def reload_module(module_path: str) -> bool:
    """
    Reload a Python module by path.

    Args:
        module_path: Path to .py file (e.g., "/path/to/music_minion/playlist.py")

    Returns:
        True if reload successful, False otherwise
    """
    # Convert file path to module name
    # "/path/to/music_minion/playlist.py" -> "music_minion.playlist"

    # Check if module is already imported
    if module_name in sys.modules:
        try:
            module = sys.modules[module_name]
            importlib.reload(module)
            return True
        except Exception as e:
            # Log error but don't crash app
            print(f"Failed to reload {module_name}: {e}")
            return False

    return False
```

### 4. State Preservation Strategy

**Critical State to Preserve** (stored in `main.py` globals):
- `current_player_state: PlayerState` - MPV connection and playback state
- `music_tracks: List[Track]` - Loaded library
- `current_config: Config` - Configuration object
- Database connection (managed by context managers, auto-reconnects)

**How Preservation Works**:
- Module reload only updates function definitions and classes
- Global instances in `main.py` are NOT reloaded (they live in `__main__`)
- Imported modules get new code, but `main.py`'s references remain stable
- Player socket connection persists because it's in `current_player_state`

**Caveat**: If you modify `PlayerState` class definition, existing instance won't update. This is acceptable for development - restart if changing core data structures.

### 5. Integration with Main Loop

**Module**: `src/music_minion/main.py`

Add command-line flag:
```python
import argparse

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dev', action='store_true',
                       help='Enable hot-reload for development')
    args = parser.parse_args()

    # Setup file watcher if --dev flag present
    observer = None
    if args.dev:
        from . import dev_reload

        def on_file_change(filepath):
            success = dev_reload.reload_module(filepath)
            if success:
                filename = Path(filepath).name
                safe_print(f"🔄 Reloaded: {filename}", style="cyan")

        observer = dev_reload.setup_file_watcher(on_file_change)
        safe_print("🔥 Hot-reload enabled", style="green bold")

    try:
        # ... existing main loop ...
        pass
    finally:
        if observer:
            dev_reload.stop_file_watcher(observer)
```

### 6. Reload Notification

When a file is reloaded:
- Print subtle notification: `🔄 Reloaded: playlist.py`
- Use cyan color to distinguish from normal output
- Don't interrupt current prompt or playback
- If reload fails, show error but continue running

### 7. Manual Reload Command

Add optional `reload` command for manual module reloading:

```python
def handle_reload_command(args: List[str]) -> None:
    """Manually reload a specific module or all modules."""
    if not args:
        # Reload all music_minion modules
        modules_to_reload = [
            'playlist', 'playlist_filters', 'playlist_ai',
            'sync', 'playback', 'ai', 'ui', 'library'
        ]
        for mod in modules_to_reload:
            reload_module(f"music_minion.{mod}")
        safe_print("Reloaded all modules", style="green")
    else:
        # Reload specific module
        module_name = args[0]
        success = reload_module(f"music_minion.{module_name}")
        if success:
            safe_print(f"Reloaded {module_name}", style="green")
```

## Technical Considerations

### Import Patterns
Music Minion uses:
```python
from . import playlist
```

This means `main.py` holds references like `playlist.create_playlist()`. When `importlib.reload(playlist)` runs, the `playlist` object in `main.py`'s namespace gets updated with new code.

### What Won't Work
- Changing function signatures that are actively in call stack
- Modifying global state in reloaded modules (it gets reset)
- Changing database schema (requires migration)
- Modifying class instances that already exist (only new instances get new code)

### Error Handling
- Syntax errors in modified file: Print error, don't reload, keep old code
- Import errors: Print error, revert to previous module version if possible
- Runtime errors in reloaded code: Will surface on next command execution

### Performance
- File watching has negligible overhead (runs in background thread)
- Module reload is fast (<10ms for typical module)
- No impact on production since feature only enabled with `--dev` flag

## Usage Examples

### Example 1: Tweaking Playlist Filter Logic
1. Start app: `music-minion --dev`
2. Create smart playlist with BPM filter
3. Notice filter logic is wrong
4. Edit `src/music_minion/playlist_filters.py`
5. Save file
6. See: `🔄 Reloaded: playlist_filters.py`
7. Test filter again - new logic applied immediately

### Example 2: Updating AI Prompt
1. Running with `--dev` flag
2. Test AI playlist parsing
3. Edit prompt in `src/music_minion/playlist_ai.py`
4. Save file
5. See: `🔄 Reloaded: playlist_ai.py`
6. Test AI parsing again with new prompt

### Example 3: Manual Reload
1. Running with `--dev` flag
2. Make multiple changes to several files
3. Type: `reload`
4. All modules reloaded at once

## File Structure

```
music-minion/
├── src/music_minion/
│   ├── dev_reload.py         # NEW: File watcher and reload logic
│   ├── main.py               # MODIFIED: Add --dev flag, watcher integration
│   └── ...                   # All other modules remain unchanged
├── docs/
│   └── hot-reload-implementation.md  # This document
└── pyproject.toml            # MODIFIED: Add watchdog to dev dependencies
```

## Development Workflow

### Before Hot Reload
1. Edit code
2. Exit app (Ctrl+C)
3. Restart app
4. Navigate back to test case
5. Test change
6. Repeat

### After Hot Reload
1. Start once: `music-minion --dev`
2. Edit code
3. Save file (automatic reload)
4. Test change immediately
5. Repeat steps 2-4

**Time saved**: ~5-10 seconds per iteration, significant over a dev session.

## Limitations & Trade-offs

### Acceptable Limitations
- Can't reload class definitions for already-instantiated objects
- Database schema changes still require restart
- Changes to `main.py` itself require restart (watching the watcher)
- Global state in reloaded modules gets reset

### Unacceptable Scenarios (Must Restart)
- Changing database schema version
- Modifying `PlayerState` class structure
- Adding new dependencies to `pyproject.toml`
- Changing entry point or command-line parsing

### Development-Only Feature
- Not available in production installs
- Only activated with `--dev` flag
- No performance impact when disabled
- No security concerns (local development only)

## Testing Strategy

### Manual Testing
1. Start with `--dev` flag
2. Modify each major module individually
3. Verify reload notification appears
4. Verify updated code executes correctly
5. Verify state preservation (track keeps playing, database intact)

### Edge Cases to Test
- Syntax error in modified file (should not crash app)
- Rapid successive saves (debouncing works)
- Modifying file during command execution
- Reloading module that's currently imported by another

### Success Criteria
- Code changes visible within 1 second of save
- No crashes from reload failures
- Player state preserved across reloads
- Clear feedback when reload succeeds/fails

## Future Enhancements

### Watch Configuration Files
Extend to also watch `~/.config/music-minion/*.toml` and reload config on change.

### Smart Dependency Reloading
If `playlist.py` changes and imports `playlist_filters.py`, reload both modules in dependency order.

### Reload History
Track what modules were reloaded and when, accessible via `reload history` command.

### Hot-Patch Testing
Allow reloading test files and re-running tests without exiting pytest session.
