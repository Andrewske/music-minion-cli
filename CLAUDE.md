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

**Global Player**:
Frontend-driven player with cross-device control (Spotify Connect style):
- **playerStore**: Zustand store for playback state (current track, queue, playback status)
- **PlayerBar**: Persistent bottom bar with controls across all pages
- **Cross-device sync**: WebSocket broadcasts state to all connected devices
- **State management**: Pure functional updates, no mutations

Key files:
- `web/frontend/src/stores/playerStore.ts` - Zustand store for player state
- `web/frontend/src/components/player/PlayerBar.tsx` - Persistent player controls
- `web/backend/routers/player.py` - Backend API for player state sync

API endpoints:
- `GET /api/player/devices` - List all connected devices
- `GET /api/player/state` - Get current player state
- `POST /api/player/play` - Start playback
- `POST /api/player/pause` - Pause playback
- `POST /api/player/skip` - Skip to next track
- `POST /api/player/queue` - Add to queue

**Global Sidebar Navigation**:
Frontend collapsible sidebar with persistent state:
- **Sidebar**: Collapsible between icons-only (72px) and expanded (280px) modes
- **filterStore**: Zustand store for global track filtering across routes
- **SidebarPlaylists**: Collapsible playlist list with active state highlighting
- **SidebarFilters**: Collapsible filter section using global store
- **Mobile**: Hamburger menu with slide-out sheet (Radix Dialog)
- **State persistence**: Sidebar expand/collapse state saved to localStorage

Key files:
- `web/frontend/src/stores/filterStore.ts` - Global filter state
- `web/frontend/src/components/sidebar/Sidebar.tsx` - Main sidebar container
- `web/frontend/src/components/sidebar/MobileHeader.tsx` - Mobile hamburger menu
- `web/frontend/src/routes/__root.tsx` - Layout integration

Pattern: Sidebar content affects multiple routes via Zustand stores, not props drilling.

## Files

- Database: SQLite v31 at `~/.local/share/music-minion/music_minion.db` (schema in `core/database.py`)
- Learnings: `ai-learnings.md`
- Future roadmap: `docs/incomplete-items.md`

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (90-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk vitest run          # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%)
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->