---
task: 02-crud-functions
status: done
depends: [01-database-migration]
files:
  - path: src/music_minion/domain/playlists/crud.py
    action: modify
---

# CRUD Functions for Pinning

## Context
Add pin/unpin/reorder functions to the playlist CRUD layer. These functions manage the `pin_order` column and handle position shifting when playlists are pinned/unpinned/reordered.

## Files to Modify/Create
- src/music_minion/domain/playlists/crud.py (modify)

## Implementation Details

**Step 1: Update get_all_playlists to sort by pin_order**

Modify the ORDER BY in `get_all_playlists()` (~line 277):

```python
ORDER BY (pin_order IS NULL), pin_order, name
```

And add `pin_order` to SELECT (~line 262):
```python
SELECT
    id,
    name,
    type,
    description,
    track_count,
    created_at,
    updated_at,
    last_played_at,
    library,
    pin_order
FROM playlists
```

**Step 2: Add pin_playlist function**

```python
def pin_playlist(playlist_id: int, position: int | None = None) -> bool:
    """
    Pin a playlist to the top of the list.

    Args:
        playlist_id: ID of playlist to pin
        position: Optional position (1-indexed). If None, appends to end of pinned list.

    Returns:
        True if successful
    """
    with get_db_connection() as conn:
        if position is None:
            # Get next available position
            cursor = conn.execute(
                "SELECT COALESCE(MAX(pin_order), 0) + 1 FROM playlists WHERE pin_order IS NOT NULL"
            )
            position = cursor.fetchone()[0]

        conn.execute(
            "UPDATE playlists SET pin_order = ? WHERE id = ?",
            (position, playlist_id)
        )
        conn.commit()
        return True
```

**Step 3: Add unpin_playlist function**

```python
def unpin_playlist(playlist_id: int) -> bool:
    """
    Unpin a playlist and reorder remaining pinned playlists.

    Args:
        playlist_id: ID of playlist to unpin

    Returns:
        True if successful
    """
    with get_db_connection() as conn:
        # Get current pin_order before unpinning
        cursor = conn.execute(
            "SELECT pin_order FROM playlists WHERE id = ?", (playlist_id,)
        )
        row = cursor.fetchone()
        if not row or row[0] is None:
            return False  # Already unpinned

        old_position = row[0]

        # Unpin the playlist
        conn.execute("UPDATE playlists SET pin_order = NULL WHERE id = ?", (playlist_id,))

        # Shift down all playlists that were after this one
        conn.execute(
            "UPDATE playlists SET pin_order = pin_order - 1 WHERE pin_order > ?",
            (old_position,)
        )
        conn.commit()
        return True
```

**Step 4: Add reorder_pinned_playlist function**

```python
def reorder_pinned_playlist(playlist_id: int, new_position: int) -> bool:
    """
    Move a pinned playlist to a new position.

    Args:
        playlist_id: ID of playlist to move
        new_position: New 1-indexed position

    Returns:
        True if successful
    """
    with get_db_connection() as conn:
        # Get current position
        cursor = conn.execute(
            "SELECT pin_order FROM playlists WHERE id = ?", (playlist_id,)
        )
        row = cursor.fetchone()
        if not row or row[0] is None:
            return False  # Not pinned

        old_position = row[0]
        if old_position == new_position:
            return True  # No change needed

        if new_position > old_position:
            # Moving down: shift items between old+1 and new up by 1
            conn.execute(
                """UPDATE playlists SET pin_order = pin_order - 1
                   WHERE pin_order > ? AND pin_order <= ?""",
                (old_position, new_position)
            )
        else:
            # Moving up: shift items between new and old-1 down by 1
            conn.execute(
                """UPDATE playlists SET pin_order = pin_order + 1
                   WHERE pin_order >= ? AND pin_order < ?""",
                (new_position, old_position)
            )

        # Set new position
        conn.execute(
            "UPDATE playlists SET pin_order = ? WHERE id = ?",
            (new_position, playlist_id)
        )
        conn.commit()
        return True
```

**Step 5: Commit**

```bash
git add src/music_minion/domain/playlists/crud.py
git commit -m "feat: add pin/unpin/reorder CRUD functions for playlists"
```

## Verification

Test via Python REPL:
```bash
uv run python -c "
from music_minion.domain.playlists import crud
playlists = crud.get_all_playlists()
print('pin_order' in playlists[0] if playlists else 'No playlists')
"
```
Expected: `True` (pin_order field exists in playlist dict)
