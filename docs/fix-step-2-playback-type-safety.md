# Step 2: Fix Type Safety Issues in playback.py

**Priority**: CRITICAL + IMPORTANT
**File**: `src/music_minion/commands/playback.py`
**Estimated Time**: 15 minutes

## Issues to Fix

### Issue 1: Anti-pattern with Ellipsis Sentinel (Line 106)

**Severity**: Critical
**Location**: Line 106 in `play_track()` function signature

**Problem**:
The function uses ellipsis (`...`) as a sentinel value to distinguish between "not provided", `None`, and an actual int. This is fragile, type-unsafe, and non-idiomatic Python. Type checkers struggle with this pattern.

**Current Code**:
```python
def play_track(
    ctx: AppContext,
    track: library.Track,
    playlist_position: Optional[int] = None,
    force_playlist_id: Optional[int | None] = ...,
) -> Tuple[AppContext, bool]:
```

And later in the function (around line 257-263):
```python
# Get playlist ID for session tracking
# Use force_playlist_id if explicitly provided, otherwise auto-detect active playlist
if force_playlist_id is not ...:
    playlist_id = force_playlist_id
else:
    active_playlist = playlists.get_active_playlist()
    playlist_id = active_playlist["id"] if active_playlist else None
```

**Fix**: Use a proper sentinel object pattern.

**Expected Result**:

At the top of the file (after imports, before functions):
```python
# Sentinel for force_playlist_id parameter to distinguish "not provided" from None
_UNSET = object()
```

Update function signature:
```python
def play_track(
    ctx: AppContext,
    track: library.Track,
    playlist_position: Optional[int] = None,
    force_playlist_id: Optional[int] | object = _UNSET,
) -> Tuple[AppContext, bool]:
```

Update the logic that checks for the sentinel:
```python
# Get playlist ID for session tracking
# Use force_playlist_id if explicitly provided, otherwise auto-detect active playlist
if force_playlist_id is not _UNSET:
    playlist_id = force_playlist_id
else:
    active_playlist = playlists.get_active_playlist()
    playlist_id = active_playlist["id"] if active_playlist else None
```

---

### Issue 2: Missing Parameter Documentation (Line 115)

**Severity**: Important
**Location**: Docstring for `play_track()` function

**Problem**:
The `force_playlist_id` parameter is not documented in the docstring, and its behavior is confusing without explanation.

**Current Docstring**:
```python
"""
Play a specific track.

Args:
    ctx: Application context
    track: Track to play
    playlist_position: Optional 0-based position in active playlist
    force_playlist_id: Force playlist_id for session tracking (use None for comparison mode, ... for auto-detect)

Returns:
    (updated_context, should_continue)
"""
```

**Fix**: Update docstring to explain the new sentinel pattern clearly.

**Expected Result**:
```python
"""
Play a specific track.

Args:
    ctx: Application context
    track: Track to play
    playlist_position: Optional 0-based position in active playlist
    force_playlist_id: Force playlist_id for session tracking.
        - Omit (default): Auto-detect from active playlist
        - None: Force no playlist context (e.g., comparison mode)
        - int: Use specific playlist ID

Returns:
    (updated_context, should_continue)
"""
```

---

## Implementation Steps

1. **Add sentinel constant** (Issue 1):
   - Open `src/music_minion/commands/playback.py`
   - After the import statements and before any function definitions, add:
     ```python
     # Sentinel for force_playlist_id parameter to distinguish "not provided" from None
     _UNSET = object()
     ```

2. **Update function signature** (Issue 1):
   - Navigate to line 100-106 in `play_track()` function
   - Change `force_playlist_id: Optional[int | None] = ...` to `force_playlist_id: Optional[int] | object = _UNSET`

3. **Update sentinel check** (Issue 1):
   - Navigate to lines 257-263 (the if statement checking `force_playlist_id`)
   - Replace `if force_playlist_id is not ...:` with `if force_playlist_id is not _UNSET:`

4. **Update docstring** (Issue 2):
   - Navigate to the docstring for `play_track()` (around lines 102-115)
   - Replace the `force_playlist_id` documentation with the improved version above

## Verification

After making changes, verify:
1. Type checker passes: The code should type-check correctly
2. All existing tests pass (if any)
3. File compiles: `python -m py_compile src/music_minion/commands/playback.py`
4. Manually test:
   - Playing a track without specifying `force_playlist_id` (should auto-detect)
   - Playing a track with `force_playlist_id=None` (should force no playlist)
   - Playing a track with `force_playlist_id=123` (should use that playlist)

## Testing Commands

```bash
# Compile check
python -m py_compile src/music_minion/commands/playback.py

# Type check (if using mypy/pyright)
mypy src/music_minion/commands/playback.py
```

## References

- PEP 661: Sentinel values (explains why object() is preferred over ellipsis)
- Project CLAUDE.md: "Type hints required for parameters and returns"
