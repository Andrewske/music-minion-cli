# Create Web Process Manager Module

## Files to Create
- `src/music_minion/web_launcher.py` (new)

## Implementation Details

Create a new module with pure functions for web process lifecycle management. This module will handle starting/stopping the FastAPI backend and Vite frontend as subprocesses.

### Functions to Implement

#### 1. `is_port_available(port: int) -> bool`
Check if a port is available for binding.

```python
import socket

def is_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False
```

#### 2. `check_web_prerequisites() -> tuple[bool, str]`
Validate that all required dependencies and resources are available.

**Checks:**
- npm is installed (`shutil.which('npm')`)
- uvicorn is available in uv environment (`uv run which uvicorn`)
- Port 8000 is available (FastAPI backend)
- Port 5173 is available (Vite frontend)
- `web/frontend/package.json` exists

**Returns:**
- `(True, "")` if all checks pass
- `(False, "error message")` with specific error if any check fails

**Error Messages:**
- "npm not found. Install Node.js first."
- "uvicorn not found in uv environment."
- "Port 8000 already in use (FastAPI backend)"
- "Port 5173 already in use (Vite frontend)"
- "Frontend directory not found. Run from project root."

#### 3. `start_uvicorn_process() -> subprocess.Popen`
Start the FastAPI backend server.

**Command:** `uv run uvicorn web.backend.main:app --host 0.0.0.0 --port 8000 --reload`

**Configuration:**
- Working directory: Project root
- Log redirection: `/tmp/music-minion-uvicorn.log`
- Open log file in write mode ("w" to overwrite stale logs)
- Merge stderr into stdout: `stderr=subprocess.STDOUT`

**Returns:** `subprocess.Popen` instance

#### 4. `start_vite_process() -> subprocess.Popen`
Start the Vite frontend dev server.

**Command:** `npm run dev -- --host`

**Configuration:**
- Working directory: `web/frontend/`
- Log redirection: `/tmp/music-minion-vite.log`
- Open log file in write mode ("w" to overwrite stale logs)
- Merge stderr into stdout: `stderr=subprocess.STDOUT`

**Returns:** `subprocess.Popen` instance

#### 5. `start_web_processes() -> tuple[subprocess.Popen, subprocess.Popen]`
Convenience function to start both processes.

**Returns:** `(uvicorn_proc, vite_proc)` tuple

#### 6. `stop_web_processes(uvicorn_proc: subprocess.Popen, npm_proc: subprocess.Popen) -> None`
Gracefully stop both web processes.

**Shutdown Sequence:**
1. Send `proc.terminate()` (SIGTERM) to each subprocess
2. Wait 5 seconds for graceful shutdown via `proc.wait(timeout=5)`
3. If timeout exceeded, force kill with `proc.kill()`
4. Catch and ignore errors from already-terminated processes

## Technical Details

**Imports needed:**
```python
import subprocess
import socket
import shutil
from pathlib import Path
from typing import Optional
```

**Project root detection:**
```python
# Detect project root (where pyproject.toml exists)
PROJECT_ROOT = Path(__file__).parent.parent.parent
```

**Log file paths:**
```python
UVICORN_LOG = Path("/tmp/music-minion-uvicorn.log")
VITE_LOG = Path("/tmp/music-minion-vite.log")
```

## Acceptance Criteria

✅ All functions have explicit return type annotations
✅ Port checking works correctly (test with occupied ports)
✅ Prerequisite checks fail fast with clear error messages
✅ Subprocess logs redirect to `/tmp/music-minion-*.log` files
✅ Graceful shutdown sends SIGTERM and waits before force kill
✅ No global state or class instances (pure functions only)
✅ Handles already-terminated processes without crashing

## Dependencies
None - this is the foundational module.
