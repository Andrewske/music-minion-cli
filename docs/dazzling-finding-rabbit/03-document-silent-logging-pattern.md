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

Add documentation to `safe_print()` function in `core/output.py` to clarify this is an intentional pattern for thread coordination.

### Changes to output.py

Add to `safe_print()` docstring (after line 115):

```python
def safe_print(message: str = "", style: Optional[str] = None) -> None:
    """Print message with optional style (bypasses blessed UI, respects silent_logging).

    Thread Safety:
        Background threads can set `threading.current_thread().silent_logging = True`
        to suppress stdout output during blessed UI mode. This is a custom attribute
        used for coordination between threads and the terminal UI.

        Examples: See commands/library.py:71, commands/rating.py:116, ipc/server.py:150

    Args:
        message: Text to print to stdout
        style: Optional style name from STYLES dict (e.g., 'red', 'green', 'yellow')
    """
```

### Rationale
This documents the intentional design pattern rather than trying to "fix" something that's working correctly. The `silent_logging` attribute is a lightweight thread-coordination mechanism that avoids the complexity of thread-local storage.

## Acceptance Criteria

- [ ] Docstring updated in `src/music_minion/core/output.py`
- [ ] Documentation mentions thread safety and custom attribute
- [ ] References to example usage locations included
- [ ] `ruff check src` passes with no new type errors
- [ ] No functional changes - documentation only

## Dependencies
None - documentation-only change

## Verification Commands

```bash
# Verify docstring added
rg -A10 "def safe_print" src/music_minion/core/output.py

# Verify no new type errors
uv run ruff check src/music_minion/core/output.py

# Verify pattern is still used correctly
rg "silent_logging = True" src/music_minion/
```
