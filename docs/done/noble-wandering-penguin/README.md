# Implementation Tasks: Add --web Flag to music-minion CLI

**Goal:** Simplify web UI development by adding a `--web` flag that starts blessed UI + FastAPI backend + Vite frontend in a single command.

**From 3 terminals → 1 terminal:**
```bash
# Before
uv run music-minion
uv run uvicorn web.backend.main:app --host 0.0.0.0 --port 8000 --reload
cd web/frontend && npm run dev -- --host

# After
uv run music-minion --web
```

## Task Sequence

Execute tasks in numerical order:

1. **[01-create-web-launcher-module.md](01-create-web-launcher-module.md)**
   - Create `src/music_minion/web_launcher.py` with pure functions for process lifecycle
   - Port checking, prerequisite validation, subprocess management

2. **[02-add-web-flag-to-cli.md](02-add-web-flag-to-cli.md)**
   - Add `--web` flag to argument parser in `src/music_minion/cli.py`
   - Set `MUSIC_MINION_WEB_MODE` environment variable

3. **[03-integrate-web-process-lifecycle.md](03-integrate-web-process-lifecycle.md)**
   - Integrate web launcher in `src/music_minion/main.py`
   - Start web processes after database init, stop on cleanup

4. **[04-add-web-configuration-optional.md](04-add-web-configuration-optional.md)** *(Optional)*
   - Add `WebConfig` dataclass to `src/music_minion/core/config.py`
   - Allow customizable ports and reload settings
   - Can be implemented later or skipped

5. **[05-update-documentation.md](05-update-documentation.md)**
   - Update `CLAUDE.md` Development Workflow section
   - Document new `--web` flag in Commands list

6. **[06-testing-and-validation.md](06-testing-and-validation.md)**
   - 10 manual test cases covering happy path and edge cases
   - Validation of all functionality
   - Optional: Unit tests for `web_launcher.py`

## Architecture

**Approach:** Subprocess + Threading Hybrid
- Use `subprocess.Popen` for uvicorn and npm (matches existing MPV pattern)
- Redirect logs to `/tmp/music-minion-{uvicorn,vite}.log`
- Graceful shutdown via SIGTERM when blessed UI exits

**Why blessed UI runs:**
- IPC server (Unix socket + WebSocket on port 8765) starts with blessed UI
- Web frontend uses WebSocket for hotkey commands
- User wants concurrent blessed UI + web services

## Success Criteria

✅ Single command (`music-minion --web`) starts all three services
✅ Blessed UI remains fully functional and responsive
✅ Web UI accessible at http://localhost:5173
✅ IPC commands work (web-playpause, web-winner, web-archive)
✅ Graceful shutdown when quitting blessed UI
✅ Clear error messages for missing dependencies or port conflicts
✅ Logs captured to separate files, not cluttering terminal

## Quick Start

```bash
# Execute tasks in order
cat docs/noble-wandering-penguin/01-create-web-launcher-module.md
# ... implement ...

cat docs/noble-wandering-penguin/02-add-web-flag-to-cli.md
# ... implement ...

# Continue through task 06
```

## Notes

- Task 04 (configuration) is optional - core functionality works without it
- All tasks follow functional programming style (pure functions, no classes)
- Tasks 01-03 are the minimum viable implementation
- Task 06 provides comprehensive validation before considering complete
