# Testing and Validation

## Testing Checklist

This is the final validation phase to ensure all functionality works correctly and edge cases are handled.

### Manual Test Cases

#### 1. Happy Path
**Test:** `music-minion --web` starts all three services, quit blessed UI stops all

**Steps:**
1. Run `music-minion --web`
2. Verify startup messages show backend/frontend URLs
3. Verify blessed UI appears and is functional
4. Open browser to `http://localhost:5173` and verify web UI loads
5. Start a comparison session in web UI
6. Quit blessed UI (ESC key or quit command)
7. Verify all processes stop (check `ps aux | grep uvicorn` and `ps aux | grep vite`)

**Expected:** Clean startup, all services accessible, clean shutdown

---

#### 2. Missing npm
**Test:** Clear error message when npm is not installed

**Steps:**
1. Temporarily rename npm binary: `sudo mv /usr/bin/npm /usr/bin/npm.bak`
2. Run `music-minion --web`
3. Restore npm: `sudo mv /usr/bin/npm.bak /usr/bin/npm`

**Expected:** Error message "npm not found. Install Node.js first." and immediate exit

---

#### 3. Port Conflict (Backend - 8000)
**Test:** Clear error when FastAPI port is occupied

**Steps:**
1. Start uvicorn manually: `uv run uvicorn web.backend.main:app --port 8000 &`
2. Run `music-minion --web`
3. Kill manual uvicorn: `pkill -f uvicorn`

**Expected:** Error message "Port 8000 already in use (FastAPI backend)" and immediate exit

---

#### 4. Port Conflict (Frontend - 5173)
**Test:** Clear error when Vite port is occupied

**Steps:**
1. Start a dummy server on 5173: `python3 -m http.server 5173 &`
2. Run `music-minion --web`
3. Kill dummy server: `pkill -f 'http.server 5173'`

**Expected:** Error message "Port 5173 already in use (Vite frontend)" and immediate exit

---

#### 5. Frontend Not Installed
**Test:** Error message when node_modules missing

**Steps:**
1. Rename node_modules: `mv web/frontend/node_modules web/frontend/node_modules.bak`
2. Run `music-minion --web`
3. Observe npm error in startup
4. Restore: `mv web/frontend/node_modules.bak web/frontend/node_modules`

**Expected:** Web processes attempt to start but npm fails. Check `/tmp/music-minion-vite.log` for clear npm error.

---

#### 6. Ctrl+C During Startup
**Test:** Clean shutdown of all processes when interrupted

**Steps:**
1. Run `music-minion --web`
2. Press Ctrl+C during blessed UI initialization
3. Verify all processes stopped: `ps aux | grep -E 'uvicorn|vite'`

**Expected:** All processes terminate, no orphaned subprocesses

---

#### 7. Subprocess Crash
**Test:** Blessed UI continues when web process crashes

**Steps:**
1. Run `music-minion --web`
2. Find uvicorn PID: `ps aux | grep uvicorn`
3. Kill uvicorn manually: `kill -9 <pid>`
4. Verify blessed UI still responsive
5. Check logs: `tail /tmp/music-minion-uvicorn.log`

**Expected:** Blessed UI continues working, web UI stops responding (expected)

---

#### 8. Log Files Created
**Test:** Verify log files are created and contain output

**Steps:**
1. Remove old logs: `rm /tmp/music-minion-{uvicorn,vite}.log`
2. Run `music-minion --web`
3. Check log files exist and have content:
   ```bash
   ls -lh /tmp/music-minion-uvicorn.log
   ls -lh /tmp/music-minion-vite.log
   tail -20 /tmp/music-minion-uvicorn.log
   tail -20 /tmp/music-minion-vite.log
   ```

**Expected:** Both log files exist and contain startup logs from respective processes

---

#### 9. Web UI Accessible
**Test:** Browse to frontend and verify comparison flow works

**Steps:**
1. Run `music-minion --web`
2. Open browser to `http://localhost:5173`
3. Click "Start Comparison Session"
4. Verify tracks load and audio plays
5. Make a comparison choice
6. Verify result is recorded

**Expected:** Full web UI functionality works as before

---

#### 10. IPC Commands Work
**Test:** Verify hotkey commands reach web UI via WebSocket

**Steps:**
1. Run `music-minion --web`
2. Open browser to `http://localhost:5173` and start comparison
3. In another terminal, run `music-minion web-playpause`
4. Verify audio pauses/plays in web UI
5. Run `music-minion web-winner`
6. Verify comparison is recorded

**Expected:** IPC commands trigger actions in web UI through WebSocket

---

### Automated Testing (Optional)

If desired, create unit tests for `web_launcher.py`:

**File:** `tests/test_web_launcher.py`

**Test Cases:**
- `test_is_port_available_returns_true_for_free_port()`
- `test_is_port_available_returns_false_for_occupied_port()`
- `test_check_web_prerequisites_fails_without_npm()`
- `test_check_web_prerequisites_fails_with_occupied_port()`
- `test_start_uvicorn_process_returns_popen_instance()`
- `test_stop_web_processes_sends_sigterm()`

**Mocking Strategy:**
- Mock `shutil.which()` to simulate npm missing
- Mock `socket.bind()` to simulate port conflicts
- Mock `subprocess.Popen()` to avoid actually starting processes
- Use `unittest.mock.patch()` for isolation

---

## Success Criteria

All manual test cases pass:

- ✅ Happy path: All services start and stop cleanly
- ✅ Missing npm: Clear error message
- ✅ Port conflicts: Clear error messages for both ports
- ✅ Frontend not installed: npm error in logs
- ✅ Ctrl+C: Clean shutdown
- ✅ Subprocess crash: Blessed UI continues
- ✅ Log files: Created with content
- ✅ Web UI: Accessible and functional
- ✅ IPC commands: Work through WebSocket

## Dependencies
- Tasks 01-05: All implementation and documentation complete
