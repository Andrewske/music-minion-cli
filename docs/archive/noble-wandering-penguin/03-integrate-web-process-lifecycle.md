# Integrate Web Process Lifecycle

## Files to Modify
- `src/music_minion/main.py` (modify)

## Implementation Details

Integrate the web launcher module into the main interactive mode to start and stop web processes based on the `MUSIC_MINION_WEB_MODE` environment variable.

### Changes Required

#### 1. Add web process startup (around line 535)

**Location:** In `interactive_mode()` function, after `database.init_database()`

```python
# Check if web mode enabled
web_mode = os.environ.get("MUSIC_MINION_WEB_MODE") == "1"
web_processes = None

if web_mode:
    from . import web_launcher

    # Pre-flight checks
    success, error = web_launcher.check_web_prerequisites()
    if not success:
        safe_print(f"❌ Cannot start web mode: {error}", style="red")
        sys.exit(1)

    # Start web processes
    safe_print("🌐 Starting web services...", style="cyan")
    uvicorn_proc, vite_proc = web_launcher.start_web_processes()
    web_processes = (uvicorn_proc, vite_proc)

    # Print access URLs
    safe_print("   Backend:  http://0.0.0.0:8000", style="green")
    safe_print("   Frontend: http://localhost:5173", style="green")
    safe_print("   Logs: /tmp/music-minion-{uvicorn,vite}.log", style="dim")
```

#### 2. Add web process cleanup (before line 587)

**Location:** In the `finally` block of `interactive_mode()`, after file watcher cleanup

```python
# Stop web processes if running
if web_processes:
    from . import web_launcher
    safe_print("\n🛑 Stopping web services...", style="yellow")
    web_launcher.stop_web_processes(*web_processes)
```

### Context

**Execution Flow:**
1. User runs `music-minion --web`
2. `cli.py` sets `MUSIC_MINION_WEB_MODE=1` environment variable
3. `main.py` detects environment variable and starts web processes
4. Blessed UI runs normally
5. When user quits blessed UI or Ctrl+C:
   - Blessed UI cleanup runs (existing)
   - `finally` block executes
   - Web processes stopped gracefully

**Error Handling:**
- Pre-flight checks fail → Print error, exit immediately (don't start blessed UI)
- Web processes crash during runtime → Blessed UI continues (logged to files)
- User interrupts during startup → `finally` block ensures cleanup

## Technical Details

**Variable Scope:**
- `web_processes` must be initialized before try block
- Set to `None` initially
- Only set to tuple if web mode enabled and processes started successfully
- Checked for truthiness in finally block before cleanup

**Import Strategy:**
- Import `web_launcher` only when needed (inside if block)
- Import again in finally block (defensive - handles reload scenarios)

## Acceptance Criteria

✅ Web processes start after database init, before blessed UI
✅ Clear startup messages show backend/frontend URLs and log paths
✅ Pre-flight check failures exit immediately with clear error messages
✅ Web processes stop cleanly when blessed UI exits normally
✅ Web processes stop cleanly on Ctrl+C or exception
✅ Blessed UI continues if web processes crash (check logs)
✅ No web processes start if `MUSIC_MINION_WEB_MODE` not set
✅ `web_processes` variable scope handles all code paths (try/except/finally)

## Dependencies
- Task 01: `web_launcher.py` module must exist
- Task 02: `MUSIC_MINION_WEB_MODE` environment variable must be set by CLI
