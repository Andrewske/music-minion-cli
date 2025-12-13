# Minor Code Cleanups (Suggestions)

## Files to Modify
- `src/music_minion/main.py` (modify - add TODO comment)
- `src/music_minion/domain/playback/player.py` (modify - remove stale comment)

## Implementation Details

These are low-priority cleanup tasks that improve code quality without functional changes.

### Change 1: Add TODO for Future Refactoring (main.py)

**Location**: Top of `interactive_mode()` function (around line 531)

**Problem**: Function is 246 lines long, violates ≤20 line guideline from CLAUDE.md

**Solution**: Add TODO comment for future refactoring (not implementing now)

```python
def interactive_mode() -> None:
    """Run the interactive mode with configuration.

    TODO: Refactor interactive_mode() into smaller functions
    Suggested: setup_web_mode(), setup_dev_mode(), run_blessed_ui_mode(), run_simple_mode()
    See: CLAUDE.md guideline (functions ≤20 lines)
    """
```

**Rationale**: This is a larger architectural change that should be done as a separate focused refactor. Current code works correctly, so we defer this to a future improvement cycle.

---

### Change 2: Remove Stale "NEW" Comment (player.py)

**Location**: Line 309

**Problem**: Comment `# NEW` is no longer new

**Solution**: Remove the comment

```python
# Before:
playback_started_at=time.time(),  # NEW

# After:
playback_started_at=time.time(),
```

**Rationale**: Comments like "NEW" or "TEMP" become outdated quickly and should be removed once the code is established.

## Acceptance Criteria

- [ ] TODO comment added to `interactive_mode()` function
- [ ] Stale `# NEW` comment removed from player.py
- [ ] `ruff check src` passes
- [ ] No functional changes - comments only

## Dependencies
None - these are independent cleanup tasks

## Verification Commands

```bash
# Verify TODO added
rg "TODO.*interactive_mode" src/music_minion/main.py

# Verify stale comment removed
rg "# NEW" src/music_minion/domain/playback/player.py  # Should return no results

# Run linter
uv run ruff check src/music_minion/main.py src/music_minion/domain/playback/player.py

# Verify no functional changes
git diff src/music_minion/main.py src/music_minion/domain/playback/player.py
# Should only show comment changes
```

## Notes
These changes are purely cosmetic and can be safely skipped if time is limited. They're included for completeness and to address all items from the code review.
