# Hot-Reload Usage Guide

## Overview
Hot-reload allows you to modify Python code and see changes immediately without restarting the Music Minion CLI application. This significantly speeds up the development workflow.

## Setup

### 1. Install Development Dependencies
```bash
uv pip install watchdog
```

Or install all dev dependencies:
```bash
uv sync --all-extras
```

### 2. Start with --dev Flag
```bash
music-minion --dev
```

You should see:
```
🔥 Hot-reload enabled
```

## Usage

### Making Changes
1. Edit any Python file in `src/music_minion/`
2. Save the file
3. Watch for the reload notification:
   ```
   🔄 Reloaded: playlist.py
   ```
4. Test your changes immediately - no restart needed!

### What Gets Reloaded
✅ **Reloadable** (changes take effect immediately):
- Command handlers (`commands/*.py`)
- Domain logic (`domain/*/`)
- UI components (`ui/blessed/`)
- Filters, parsers, and utilities
- Function definitions and module-level code

❌ **Not Reloadable** (require restart):
- Changes to `main.py` or `cli.py`
- Changes to `context.py` or `AppContext` structure
- Changes to `PlayerState`, `Track`, or other dataclass definitions
- Database schema changes
- New dependencies in `pyproject.toml`

### State Preservation
The following state is **preserved** across reloads:
- MPV player connection and playback
- Current track and position
- Music library list
- Database connection
- Configuration object
- blessed Terminal instance

## Examples

### Example 1: Tweaking Command Logic
```bash
# Terminal 1: Start app with hot-reload
music-minion --dev

# Terminal 2: Edit a command file
vim src/music_minion/commands/playback.py
# Make changes, save file

# Terminal 1: See reload notification
🔄 Reloaded: playback.py

# Test the command immediately
play
```

### Example 2: Updating UI Components
```bash
music-minion --dev

# Edit blessed UI component
vim src/music_minion/ui/blessed/components/dashboard.py
# Adjust layout, colors, or formatting

# See reload
🔄 Reloaded: dashboard.py

# Changes visible on next render
```

### Example 3: Fixing Filter Logic
```bash
music-minion --dev

# Create smart playlist
playlist new smart "techno" "bpm > 120"

# Notice filter isn't working right
# Edit filter code
vim src/music_minion/domain/playlists/filters.py

# Save changes
🔄 Reloaded: filters.py

# Test filter again
playlist show "techno"
# New logic applied!
```

## Troubleshooting

### Hot-Reload Not Working
**Problem**: Changes not taking effect
**Solution**: Check if module was imported:
- Only imported modules can be reloaded
- First use of a command imports its module
- Run any command that imports the module before editing

### File Not Detected
**Problem**: No reload notification appears
**Solution**:
- Ensure file is in `src/music_minion/` directory
- Check file extension is `.py`
- Wait 100ms after saving (debouncing)

### Syntax Error After Reload
**Problem**: Made a syntax error, app still running
**Solution**:
- Fix the syntax error
- Save again - it will retry the reload
- Old code remains active until successful reload

### Module Reload Failed
**Problem**: See `❌ Failed to reload` message
**Solution**:
- Check error message for details
- Common causes: syntax errors, import errors
- Fix the issue and save again
- App continues running with old code

## Performance Impact
- File watching runs in background thread (negligible CPU)
- Module reload is very fast (<10ms typical)
- No impact when `--dev` flag not used
- Production builds don't include hot-reload code

## Development Workflow

### Before Hot-Reload
1. Edit code
2. Exit app (Ctrl+C)
3. Restart app
4. Navigate back to test scenario
5. Test change
6. **Repeat 1-5** (~10 seconds per iteration)

### With Hot-Reload
1. Start once: `music-minion --dev`
2. Edit code
3. Save file (automatic reload)
4. Test change immediately
5. **Repeat 2-4** (~2 seconds per iteration)

**Time saved**: ~8 seconds per iteration
**Total saved**: 4-8 minutes per hour of development

## Technical Details

### Architecture
- Uses `watchdog` library for filesystem monitoring
- Monitors `src/music_minion/` recursively
- Debounces rapid changes (100ms delay)
- Uses `importlib.reload()` for module reloading
- Preserves global state in `main.py`

### Module Resolution
Files are converted to module names:
```
src/music_minion/commands/playlist.py
→ music_minion.commands.playlist
```

### Error Handling
- Syntax errors: Logged, old code remains active
- Import errors: Logged, old code remains active
- Runtime errors: Surface on next command execution
- App never crashes from reload failures

## Advanced Usage

### Debugging Reload Issues
Enable verbose logging to see what's happening:
```python
# Temporarily add to dev_reload.py
print(f"Attempting reload: {module_name}")
```

### Manual Reload
If you need to force-reload a module:
```python
from music_minion import dev_reload
dev_reload.reload_module("src/music_minion/commands/playlist.py")
```

### Excluding Paths
Edit `dev_reload.py` to add exclusions:
```python
if 'experimental' in event.src_path:
    return  # Skip experimental code
```

## Limitations

### Acceptable Limitations
- Can't reload class definitions for existing instances
- Database schema changes require restart
- Changes to `main.py` require restart
- Global state in reloaded modules gets reset

### When You Must Restart
- Changing database schema version
- Modifying `PlayerState`, `Track`, or other dataclass structures
- Adding new dependencies
- Changing entry point or CLI parsing
- Modifying configuration schema

## Future Enhancements

### Planned Features
- Watch configuration files (`~/.config/music-minion/*.toml`)
- Smart dependency reloading (reload imported modules)
- Reload history tracking
- Integration with test runner
- Visual indicator in blessed UI

### Potential Improvements
- Faster debouncing (<50ms)
- Selective module watching
- Reload on git branch change
- Pre-reload validation hooks
