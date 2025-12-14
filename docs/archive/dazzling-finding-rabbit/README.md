# Code Review Fixes: Implementation Tasks

This directory contains implementation-ready tasks for fixing all action items from the code review of commit 28adb911.

## Task Sequence (7 tasks)

Execute in order for best results:

### Critical Tasks (Must Fix)

1. **[01-extract-cleanup-helpers-eliminate-dry.md](01-extract-cleanup-helpers-eliminate-dry.md)**
   - Extract cleanup helpers to `helpers.py`
   - Replace 11 duplicated code blocks in `main.py`
   - **Impact**: High - Eliminates major DRY violation
   - **Files**: `src/music_minion/helpers.py`, `src/music_minion/main.py`

2. **[02-fix-websocket-logger-level.md](02-fix-websocket-logger-level.md)**
   - Revert WebSocket logger from CRITICAL to ERROR level
   - Preserve visibility of real errors
   - **Impact**: Medium - Improves error visibility
   - **Files**: `src/music_minion/ipc/server.py`

3. **[03-document-silent-logging-pattern.md](03-document-silent-logging-pattern.md)**
   - Document `silent_logging` thread attribute pattern
   - Clarify intentional design choice
   - **Impact**: Low - Documentation only
   - **Files**: `src/music_minion/core/output.py`

### Important Tasks (Should Fix)

4. **[04-add-exception-logging-mpv-cleanup.md](04-add-exception-logging-mpv-cleanup.md)**
   - Add specific exception handling to MPV cleanup
   - Log unexpected errors while allowing expected ones
   - **Impact**: Medium - Improves debugging
   - **Files**: `src/music_minion/domain/playback/player.py`

5. **[05-add-exception-logging-ui-fallback.md](05-add-exception-logging-ui-fallback.md)**
   - Add exception logging for UI fallback scenarios
   - Preserve stack traces while showing friendly messages
   - **Impact**: Medium - Improves debugging
   - **Files**: `src/music_minion/main.py`

6. **[06-document-websocket-browser-error.md](06-document-websocket-browser-error.md)**
   - Document expected browser console WebSocket error
   - Explain startup race condition and browser behavior
   - **Impact**: Low - Documentation only
   - **Files**: `web/frontend/src/hooks/useIPCWebSocket.ts`

### Suggestions (Optional)

7. **[07-minor-cleanups.md](07-minor-cleanups.md)**
   - Add TODO for future refactoring
   - Remove stale "NEW" comment
   - **Impact**: Very Low - Code hygiene
   - **Files**: `src/music_minion/main.py`, `src/music_minion/domain/playback/player.py`

## Quick Start

### Option 1: Execute All Tasks
```bash
# Review tasks
ls -1 docs/dazzling-finding-rabbit/*.md | grep -E "^[0-9]"

# Execute tasks in sequence (manually or with orchestrator)
# Start with task 01, then 02, etc.
```

### Option 2: Create Isolated Git Worktree (Recommended)
```bash
# Create isolated environment for implementation
git worktree add ../music-minion-code-review-fixes main
cd ../music-minion-code-review-fixes

# Create feature branch
git checkout -b fix/code-review-action-items

# Execute tasks from docs/dazzling-finding-rabbit/
# ...

# When done:
git add .
git commit -m "fix: address code review action items from 28adb911"
```

## Testing Strategy

### After Each Task
- Run `uv run ruff check src` to verify no new linting errors
- Check specific acceptance criteria in each task file

### Integration Testing (After All Tasks)
```bash
# Normal mode
music-minion

# Web mode
music-minion --web
# - Open browser to http://localhost:5173
# - Verify WebSocket connection
# - Check browser console for documented error (expected once)
# - Test graceful shutdown (Ctrl-C)

# Dev mode
music-minion --dev
# - Modify a Python file
# - Verify hot-reload works
# - Test graceful shutdown

# Check logs
tail -100 ~/.local/share/music-minion/logs/music-minion.log
# - No unexpected errors
# - Debug logs present for cleanup operations
```

## Success Criteria

✅ **DRY Compliance**: No duplicated cleanup code in main.py
✅ **Error Visibility**: All cleanup errors logged at debug level
✅ **Type Safety**: No new type errors from ruff/mypy
✅ **Functionality**: All modes (normal, web, dev) work as before
✅ **Documentation**: WebSocket console error documented
✅ **Tests Pass**: All existing tests pass unchanged

## Rollback Plan

All changes are non-breaking and can be reverted independently:

```bash
# Revert specific file
git checkout HEAD -- path/to/file.py

# Revert entire commit
git revert <commit-hash>
```

## Files Modified Summary

Total: 6 files modified (+ 2 documentation)

**Python Files**:
- `src/music_minion/helpers.py` - 2 new functions added
- `src/music_minion/main.py` - 11 duplicated blocks replaced, logging added
- `src/music_minion/ipc/server.py` - Logger level reverted
- `src/music_minion/core/output.py` - Docstring enhanced
- `src/music_minion/domain/playback/player.py` - Exception handling improved

**TypeScript Files**:
- `web/frontend/src/hooks/useIPCWebSocket.ts` - Comment enhanced

**Documentation** (optional):
- `docs/synthetic-shimmying-scone/02-suppress-websocket-errors-in-blessed-ui.md`

## Original Plan

Source: `.claude/plans/dazzling-finding-rabbit.md`

This task distribution was generated from the original comprehensive plan. Refer to the plan file for full context and architectural decisions.
