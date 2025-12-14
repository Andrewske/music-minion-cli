# Document silent_logging Thread Attribute Pattern

## Files to Modify
- `src/music_minion/core/output.py` (modify - add docstring section)

## Implementation Details

### Problem
Line 150 in `ipc/server.py` uses `type: ignore` for monkey-patching `threading.current_thread().silent_logging`. While this pattern is used consistently throughout the codebase, it's not centrally documented.

### Solution
The `type: ignore` is actually **correct and intentional** - this pattern is used in multiple places:
- `commands/library.py:71`
- `commands/rating.py:116`
- `ipc/server.py:150`

Add documentation to `log()` function in `core/output.py` to clarify this is an intentional pattern for thread coordination.

### Changes to output.py

Add Thread Safety section to `log()` function docstring:

```python
def log(message: str, level: str = "info") -> None:
    """
    Unified logging: writes to file AND prints for blessed UI.

    Use this instead of print() for user-facing messages that should also be logged.

    Thread Safety:
        Background threads can set `threading.current_thread().silent_logging = True`
        to suppress stdout output during blessed UI mode. This is a custom attribute
        used for coordination between threads and the terminal UI.

        Examples: See commands/library.py, commands/rating.py, ipc/server.py

    Routing logic:
    - Blessed mode + silent_logging=False: Route through UI callback (visible in command history)
    - Blessed mode + silent_logging=True: Log to file only (background threads)
    - CLI mode + silent_logging=True: Suppress output (background threads)
    - CLI mode + silent_logging=False: Print to stdout

    Args:
        message: User-facing message (can include emojis, colors, formatting)
        level: Log level (debug, info, warning, error)
    """
```

### Rationale
This documents the intentional design pattern rather than trying to "fix" something that's working correctly. The `silent_logging` attribute is a lightweight thread-coordination mechanism that avoids the complexity of thread-local storage.

## Acceptance Criteria

- [x] Docstring updated in `src/music_minion/core/output.py`
- [x] Documentation mentions thread safety and custom attribute
- [x] References to example usage locations included
- [x] `ruff check src` passes with no new type errors
- [x] No functional changes - documentation only

## Dependencies
None - documentation-only change

## Verification Commands

```bash
# Verify docstring added
rg -A15 "def log" src/music_minion/core/output.py

# Verify no new type errors
uv run ruff check src/music_minion/core/output.py

# Verify pattern is still used correctly
rg "silent_logging = True" src/music_minion/
```
