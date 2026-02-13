# Music Minion CLI

Music curation with multi-source support (local, SoundCloud, Spotify)

**Personal project**: Breaking changes OK, no backwards compatibility, delete unused code immediately

## Architecture

**Functional over Classes (CRITICAL)**:
- ALWAYS prefer functions with explicit state passing over classes
- Only use classes for: NamedTuple, dataclass, framework requirements (with justification)
- Pass state via `AppContext` dataclass, never global variables
- Pure functions: `(AppContext, str, list) -> (AppContext, bool)`

**blessed UI Rendering**:
- Three tiers: Full (track/resize/init), Input (typing/filtering), Partial (clock/progress only)
- Immutable state: All updates via `dataclasses.replace()`, never mutation
- **Always use `write_at()` for positioned output** (clears line by default, prevents overlap)

**Multi-Source Providers**:
- Pure functions only: `authenticate()`, `sync_library()`, `get_stream_url()`
- Immutable `ProviderState` dataclass
- No global variables or class instance state
- Track deduplication: TF-IDF cosine similarity

**UI Organization**:
- Keyboard handlers: `ui/blessed/events/keys/{mode}.py`
- Components: `ui/blessed/components/` (pure render functions)
- Helpers: `ui/blessed/helpers/` (scrolling, `write_at()`)
- State selectors: `ui/blessed/state_selectors.py` (memoized)
- Mode priority: comparison > wizard > builder > track_viewer > analytics > editor > normal

## Critical Patterns

**Logging (CRITICAL)**:
```python
# Background operations
from loguru import logger
logger.info("msg")
logger.exception("error")  # Auto stack traces

# User-facing (dual: file + UI)
from music_minion.core.output import log
log("✅ Success", level="info")

# Background threads
threading.current_thread().silent_logging = True
```
**NEVER use print()** - breaks blessed UI, logs lost on restart

**Message Queue** (blessed race condition fix):
```python
# core/output.py - Queue messages
_pending_history_messages: list[tuple[str, str]] = []
def log(msg, level):
    logger.log(level, msg)
    if _blessed_mode_active:
        _pending_history_messages.append((msg, color))

# executor.py - Drain after command
ctx, result = handle_command(ctx, cmd, args)
for msg, color in drain_pending_history_messages():
    ui_state = add_history_line(ui_state, msg, color)
```

**Data Loss Prevention**:
- Track ownership: `source='user'|'ai'|'file'|'soundcloud'|'spotify'`
- NEVER remove data without checking ownership
- Only remove data you own (e.g., only `source='file'` during import)

**Atomic File Operations** (Mutagen):
```python
temp_path = file_path + '.tmp'
try:
    shutil.copy2(file_path, temp_path)
    audio = MutagenFile(temp_path)
    audio.save()
    os.replace(temp_path, file_path)  # Atomic
except Exception:
    if os.path.exists(temp_path): os.remove(temp_path)
    raise
```

**Database**:
- Batch: `executemany()` (30% faster)
- Single transaction: Commit once after all updates
- Always: `with get_db_connection() as conn:`

**Error Handling**:
- `logger.exception()` in except blocks (auto stack traces)
- NEVER bare except - catch specific exceptions
- Background threads: Must wrap try/except (exceptions don't propagate)

**Progress Reporting**:
- Scale: `max(1, total // 100)` for 1% intervals
- Use callbacks for thread-safe UI updates

**Change Detection**:
- mtime: Float timestamps (sub-second precision)
- Get mtime AFTER write to capture own changes

## Commands

**Always use `uv run` for Python**

- Primary: `music-minion`
- Dev mode: `music-minion --dev` (hot-reload)
- Web mode: `music-minion --web` (blessed UI + web backend + frontend)
- IPC: `music-minion-cli play|skip|love|...`
- Opus migration: `music-minion locate-opus /path [--apply]`
- Tests: `uv run pytest` or `uv run pytest path/to/test.py::test_case`
- Lint: `uv run ruff check src` / `uv run ruff format src`

**Web Development Workflow**:
The `--web` flag starts all three services in one command:
- Blessed CLI UI (with IPC server for hotkeys)
- FastAPI backend (http://0.0.0.0:8642)
- Vite frontend (http://localhost:5173)

Logs are captured to `music-minion-{uvicorn,vite}.log` in the project root for easier debugging. All services stop gracefully when you quit the blessed UI.

**Hot-Reload** (install: `uv pip install watchdog`):
- **Reloadable**: Command handlers, domain logic, UI components, utilities
- **Not reloadable**: main.py, context.py, dataclasses, database schema
- **State preserved**: MPV, track, library, database, config
- ~8s saved per iteration

## Code Style

**Python**:
- Type hints required (params + returns)
- No circular imports
- Absolute imports preferred (`from music_minion.core import database`)
- Functions: ≤20 lines, ≤3 nesting

## Integration

**Syncthing** (Linux ↔ Windows):
- Purpose: Sync library + playlists between Music Minion (Linux) and Serato (Windows)
- Syncs: Audio files + metadata (COMMENT field), M3U8/crate playlists
- Settings: Send & Receive, Simple versioning (5-10), Watch enabled
- Reference: `docs/reference/syncthing-setup.md`
- **Auto-cleanup**: `sync local` automatically deletes `.sync-conflict-*` tracks and removes orphaned records

**File Move Detection** (automatic during `sync local`):
- Detects moved files via filename + filesize matching
- Relocates tracks preserving ratings/tags/ELO/playlist memberships
- Auto-deletes Syncthing conflict files from database
- Removes orphaned records when files deleted
- Performance: ~1.5-2s for 5000-track library

**Personal Radio** (Docker):
- Config: `docker/radio/docker-compose.yml`
- Components: Icecast (stream server) + Liquidsoap (audio player)
- **Critical**: `SCHEDULER_URL` env var must match backend port (8642)
- Liquidsoap requests tracks from `/api/radio/next-track`, reports playback via `/api/radio/track-started`
- Stream proxied through FastAPI at `/api/radio/stream` to avoid CORS
- Debugging: Check `docker logs radio-liquidsoap` for HTTP errors (523 = can't reach backend)
- Restart after config changes: `cd docker/radio && docker compose up -d --force-recreate liquidsoap`

**Pi Server Deployment** (Docker):
- URL: `https://music.piserver:8443` (via Tailscale)
- Config: `docker/pi-deployment/docker-compose.yml`
- Components: music-minion (FastAPI + static frontend), Icecast (arm64 build), Liquidsoap
- Deploy: `./scripts/deploy-to-pi.sh` (builds frontend, rsyncs, rebuilds containers)

Key files:
- `Dockerfile` - Python container with uv, includes `config.toml` for library paths
- `docker/pi-deployment/docker-compose.yml` - All 3 services for Pi
- `docker/radio/icecast-arm64/Dockerfile` - Native arm64 icecast build
- `scripts/deploy-to-pi.sh` - Deployment script

Database sync (Syncthing):
- Folder: `~/.local/share/music-minion/` (Send & Receive both sides)
- `.stignore`: `*.db-journal`, `*.db-wal`, `*.db-shm`
- WAL mode enabled for better concurrent access
- Run `sync local` on desktop to clean conflict files

Commands:
```bash
# Deploy
./scripts/deploy-to-pi.sh

# Logs
ssh piserver 'cd ~/music-minion/docker/pi-deployment && docker compose logs -f'

# Restart
ssh piserver 'cd ~/music-minion/docker/pi-deployment && docker compose restart'

# Stop
ssh piserver 'cd ~/music-minion/docker/pi-deployment && docker compose down'

# Setup daily 3am sync (run once on Pi)
ssh piserver '~/music-minion/scripts/setup-pi-cron.sh'
```

Sync API:
- `POST /api/sync` - Trigger incremental sync (changed files only)
- `POST /api/sync/full` - Full filesystem scan + export
- `GET /api/sync/status` - Check sync status

## Files

- Database: SQLite v31 in `core/database.py`
- Learnings: `ai-learnings.md`
- Future roadmap: `docs/incomplete-items.md`
