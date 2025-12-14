# Add Exception Logging for UI Fallback Errors

## Files to Modify
- `src/music_minion/main.py` (modify - lines 681-685 and 722-726)

## Implementation Details

### Problem
Lines 682 and 723 catch exceptions but only show exception message to user, losing stack trace for debugging.

### Solution
Add `logger.exception()` before user-facing messages to preserve stack traces in log file.

### Changes to main.py

**Lines 681-685** - Add logging for blessed UI fallback:

```python
# Before:
except Exception as e:
    # Blessed UI failed for other reasons, fall back to simple mode
    safe_print(
        f"⚠️  Blessed UI failed ({e}), falling back to simple mode",
        style="yellow",
    )

# After:
except Exception as e:
    # Blessed UI failed for other reasons, fall back to simple mode
    logger.exception("Blessed UI failed, falling back to simple mode")
    safe_print(
        "⚠️  Blessed UI failed, falling back to simple mode",
        style="yellow",
    )
```

**Lines 722-726** - Add logging for blessed import fallback:

```python
# Before:
except ImportError as e:
    # blessed not available, fall back to old dashboard
    safe_print(
        f"⚠️  blessed UI not available ({e}), falling back to legacy dashboard",
        style="yellow",
    )

# After:
except ImportError as e:
    # blessed not available, fall back to old dashboard
    logger.exception("blessed UI not available, falling back to legacy dashboard")
    safe_print(
        "⚠️  blessed UI not available, falling back to legacy dashboard",
        style="yellow",
    )
```

### Rationale
User sees friendly message without technical details, but developers get full stack trace in log file for debugging production issues.

## Acceptance Criteria

- [ ] `logger.exception()` added before both user-facing messages
- [ ] User messages remain user-friendly (no stack traces in terminal)
- [ ] `ruff check src` passes
- [ ] Force blessed import to fail (temporarily rename blessed module)
- [ ] Verify friendly user message displayed
- [ ] Verify full stack trace appears in log file

## Dependencies
None - independent change

## Verification Commands

```bash
# Verify changes applied
rg -B2 -A3 "Blessed UI failed" src/music_minion/main.py

# Run linter
uv run ruff check src/music_minion/main.py

# Test blessed UI fallback (simulate failure)
# Temporarily rename blessed in venv to trigger ImportError:
# mv .venv/lib/python*/site-packages/blessed .venv/lib/python*/site-packages/blessed.bak

# Run music-minion
music-minion

# Check terminal output (should see friendly message)
# Check log file for stack trace:
tail -100 ~/.local/share/music-minion/logs/music-minion.log | grep -A20 "Blessed UI"

# Restore blessed:
# mv .venv/lib/python*/site-packages/blessed.bak .venv/lib/python*/site-packages/blessed
```
