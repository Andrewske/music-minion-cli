# Step 4: Fix Type Annotations and Migration Logs in database.py

**Priority**: IMPORTANT
**File**: `src/music_minion/core/database.py`
**Estimated Time**: 10 minutes

## Issues to Fix

### Issue 1: Misleading Migration Log Messages (Lines 793, 816)

**Severity**: Important
**Location**: Lines 793 and 816 in migration functions

**Problem**:
Migration log messages say "schema version 22" and "schema version 23" but they're actually migrating TO versions 23 and 24 respectively. This is confusing for debugging.

**Current Code (Line 793)**:
```python
if current_version < 23:
    # Migration from v22 to v23: Add metadata change tracking
    logger.info(
        "Migrating database to schema version 22 (metadata change tracking)..."
    )
```

**Fix**:
```python
if current_version < 23:
    # Migration from v22 to v23: Add metadata change tracking
    logger.info(
        "Migrating database to schema version 23 (metadata change tracking)..."
    )
```

**Current Code (Line 816)**:
```python
if current_version < 24:
    # Migration from v23 to v24: Add playback session tracking table
    logger.info(
        "Migrating database to schema version 23 (playback session tracking)..."
    )
```

**Fix**:
```python
if current_version < 24:
    # Migration from v23 to v24: Add playback session tracking table
    logger.info(
        "Migrating database to schema version 24 (playback session tracking)..."
    )
```

Also update the completion log (around line 838):
```python
logger.info("Migration to schema version 23 complete")
```

**Fix**:
```python
logger.info("Migration to schema version 24 complete")
```

---

### Issue 2: Old-Style Type Hints (Line 1607)

**Severity**: Important
**Location**: Line 1607 in `get_top_tracks_by_time()` function signature

**Problem**:
Uses old-style `List[Dict[str, Any]]` instead of modern `list[dict[str, Any]]`. Project uses modern Python type hints throughout.

**Current Code**:
```python
def get_top_tracks_by_time(
    days: int = 30, limit: int = 20
) -> List[Dict[str, Any]]:
```

**Fix**:
```python
def get_top_tracks_by_time(
    days: int = 30, limit: int = 20
) -> list[dict[str, Any]]:
```

You may need to check the imports at the top of the file. If `List` and `Dict` are imported from `typing`, they might no longer be needed:

**Current imports** (if they exist):
```python
from typing import List, Dict, Optional, Any, ...
```

**Fix** (if List/Dict are no longer used elsewhere):
```python
from typing import Optional, Any, ...
```

---

### Issue 3: Missing Return Type Annotation (Line 1624)

**Severity**: Important
**Location**: Line 1624 in `get_playlist_listening_stats()` function

**Problem**:
Function is missing return type annotation. Project CLAUDE.md requires "Explicit return types required".

**Current Code**:
```python
def get_playlist_listening_stats():
    """Get listening statistics grouped by playlist."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                playlist_id,
                COUNT(*) as sessions,
                SUM(seconds_played) as total_seconds
            FROM track_listen_sessions
            WHERE playlist_id IS NOT NULL
            GROUP BY playlist_id
        """
        )
        return [dict(row) for row in cursor.fetchall()]
```

**Fix**:
```python
def get_playlist_listening_stats() -> list[dict[str, Any]]:
    """Get listening statistics grouped by playlist.

    Returns:
        List of dicts with: playlist_id, sessions, total_seconds
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                playlist_id,
                COUNT(*) as sessions,
                SUM(seconds_played) as total_seconds
            FROM track_listen_sessions
            WHERE playlist_id IS NOT NULL
            GROUP BY playlist_id
        """
        )
        return [dict(row) for row in cursor.fetchall()]
```

---

## Implementation Steps

1. **Fix migration log for v23** (Issue 1):
   - Open `src/music_minion/core/database.py`
   - Navigate to line ~793
   - Change `"schema version 22"` to `"schema version 23"`

2. **Fix migration logs for v24** (Issue 1):
   - Navigate to line ~816
   - Change `"schema version 23"` to `"schema version 24"`
   - Navigate to line ~838
   - Change `"Migration to schema version 23 complete"` to `"Migration to schema version 24 complete"`

3. **Update type hints in `get_top_tracks_by_time()`** (Issue 2):
   - Navigate to line ~1607
   - Change `List[Dict[str, Any]]` to `list[dict[str, Any]]`

4. **Add return type to `get_playlist_listening_stats()`** (Issue 3):
   - Navigate to line ~1624
   - Add `-> list[dict[str, Any]]:` to the function signature
   - Update docstring to include Returns section

5. **Clean up imports** (Issue 2):
   - Navigate to the top of the file
   - Check if `List` and `Dict` are imported from `typing`
   - If they're no longer used anywhere in the file, remove them from imports
   - Keep this for later: You can search the file for `List[` and `Dict[` to check

## Verification

After making changes, verify:

1. **Migration logs are correct**:
   ```bash
   # Check the migration log messages are now correct
   grep -n "schema version" src/music_minion/core/database.py
   ```
   Should show v23 and v24 in the right places.

2. **Type hints are modern**:
   ```bash
   # Check for old-style type hints
   grep "List\[" src/music_minion/core/database.py  # Should be minimal/none
   grep "Dict\[" src/music_minion/core/database.py  # Should be minimal/none
   ```

3. **All functions have return types**:
   ```bash
   # Compile check
   python -m py_compile src/music_minion/core/database.py
   ```

4. **Type checker passes** (if using mypy/pyright):
   ```bash
   mypy src/music_minion/core/database.py
   ```

## References

- Project CLAUDE.md: "Explicit return types required"
- Project CLAUDE.md: "Type inference where it improves readability"
- PEP 585: Type Hinting Generics In Standard Collections (list vs List)
