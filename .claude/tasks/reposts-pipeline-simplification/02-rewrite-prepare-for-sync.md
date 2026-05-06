---
task: 02-rewrite-prepare-for-sync
status: pending
depends: []
files:
  - path: web/backend/discovery_sync.py
    action: modify
---

# Rewrite `prepare_for_sync` to Use SC IDs Natively

## Context

Partial-refill semantics (option B) preserved: kept tracks stay, fresh fills cleared slots. Internals rewritten to return `(target_count, kept_sc_ids)` and let `run_discovery_sync` (Step 4) compose `kept + fresh` for the SC push. No SC API call in this function.

Adds `dry_run` param so `run_discovery_sync(dry_run=True)` no longer mutates `playlist_tracks` or bucket state. Preserves existing side effects in wet-run mode: `mark_tracks_liked/dismissed`, `recalculate_artist_stats`, `playlists.track_count` update, DELETE assigned tracks.

## Files to Modify/Create

- `web/backend/discovery_sync.py` (modify) — rewrite `prepare_for_sync`, factor `_process_bucket_assignments` helper

## Implementation Details

Replace existing `prepare_for_sync` (currently at `discovery_sync.py:36`) with:

```python
def prepare_for_sync(
    playlist_id: int,
    dry_run: bool = False,
) -> tuple[int, list[str]]:
    """Return (target_count_for_fresh, kept_sc_ids_in_position_order).

    No active session: full replace (delete all if not dry_run, target=100, kept=[]).
    Active session: process bucket assignments (if not dry_run), return remaining
    kept count + ids.

    `dry_run=True` skips all writes — no DELETEs, no `mark_tracks_*`, no
    `recalculate_artist_stats`, no `track_count` update.
    """
    target = 100
    with get_db_connection() as conn:
        session = conn.execute(
            "SELECT id FROM bucket_sessions WHERE playlist_id = ? AND status = 'active'",
            (playlist_id,),
        ).fetchone()

        if not session:
            if not dry_run:
                conn.execute(
                    "DELETE FROM playlist_tracks WHERE playlist_id = ?",
                    (playlist_id,),
                )
                conn.execute(
                    """UPDATE playlists SET track_count = 0 WHERE id = ?""",
                    (playlist_id,),
                )
                conn.commit()
            return target, []

        session_id = session["id"]
        if not dry_run:
            _process_bucket_assignments(conn, session_id, playlist_id)

        kept_rows = conn.execute(
            """SELECT t.soundcloud_id
               FROM playlist_tracks pt
               JOIN tracks t ON t.id = pt.track_id
               WHERE pt.playlist_id = ? AND t.soundcloud_id IS NOT NULL
               ORDER BY pt.position""",
            (playlist_id,),
        ).fetchall()
        kept_sc_ids = [r["soundcloud_id"] for r in kept_rows]
        target_count = max(0, target - len(kept_sc_ids))
        return target_count, kept_sc_ids
```

Factor `_process_bucket_assignments(conn, session_id, playlist_id)` from the inlined bucket-handling block currently inside `prepare_for_sync`. **Must preserve all existing side effects**:

```python
def _process_bucket_assignments(conn, session_id: int, playlist_id: int) -> None:
    """Mark liked/dismissed via buckets, recalculate stats, prune playlist_tracks,
    update track_count. Wet-run only (caller gates on dry_run).
    """
    buckets = conn.execute(
        """SELECT b.id, b.name, bpl.playlist_id as linked_playlist_id
        FROM buckets b
        LEFT JOIN bucket_playlist_links bpl ON bpl.bucket_id = b.id
        WHERE b.session_id = ?""",
        (session_id,),
    ).fetchall()

    liked_sc_ids: list[str] = []
    dismissed_sc_ids: list[str] = []
    for bucket in buckets:
        rows = conn.execute(
            """SELECT t.soundcloud_id FROM bucket_tracks bt
            JOIN tracks t ON t.id = bt.track_id
            WHERE bt.bucket_id = ? AND t.soundcloud_id IS NOT NULL""",
            (bucket["id"],),
        ).fetchall()
        sc_ids = [r["soundcloud_id"] for r in rows]
        if bucket["linked_playlist_id"]:
            liked_sc_ids.extend(sc_ids)
        else:
            dismissed_sc_ids.extend(sc_ids)

    if liked_sc_ids:
        discovery_queries.mark_tracks_liked(liked_sc_ids)
    if dismissed_sc_ids:
        discovery_queries.mark_tracks_dismissed(dismissed_sc_ids)
    if liked_sc_ids or dismissed_sc_ids:
        discovery_queries.recalculate_artist_stats()

    assigned_rows = conn.execute(
        """SELECT bt.track_id FROM bucket_tracks bt
        JOIN buckets b ON b.id = bt.bucket_id
        WHERE b.session_id = ?""",
        (session_id,),
    ).fetchall()
    assigned_ids = [r["track_id"] for r in assigned_rows]
    if assigned_ids:
        placeholders = ",".join("?" * len(assigned_ids))
        conn.execute(
            f"DELETE FROM playlist_tracks WHERE playlist_id = ? AND track_id IN ({placeholders})",
            [playlist_id, *assigned_ids],
        )
        conn.execute(
            """UPDATE playlists SET track_count = (
                SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id = ?
            ) WHERE id = ?""",
            (playlist_id, playlist_id),
        )
        conn.commit()
        logger.info(f"Removed {len(assigned_ids)} assigned tracks from playlist_tracks")
```

Update any callers / type hints. Return shape changed — old call sites will break loudly, which is the intent (Step 4 fixes the only caller).

## Verification

```bash
# Imports clean, signature visible, dry_run param present
uv run python -c "
import inspect
from web.backend.discovery_sync import prepare_for_sync
sig = inspect.signature(prepare_for_sync)
print('sig:', sig)
assert 'dry_run' in sig.parameters, 'missing dry_run'
print('returns tuple? ', 'tuple' in str(sig.return_annotation))
"

# Dry-run does not mutate (smoke against live DB):
uv run python -c "
import sqlite3
from pathlib import Path
from web.backend.discovery_sync import prepare_for_sync
db = Path.home() / '.local/share/music-minion/music_minion.db'
con = sqlite3.connect(db); con.row_factory = sqlite3.Row
before = con.execute('SELECT COUNT(*) AS n FROM playlist_tracks WHERE playlist_id = 26').fetchone()['n']
target, kept = prepare_for_sync(26, dry_run=True)
after = con.execute('SELECT COUNT(*) AS n FROM playlist_tracks WHERE playlist_id = 26').fetchone()['n']
assert before == after, f'dry_run mutated: {before} -> {after}'
print(f'dry_run OK; target={target} kept={len(kept)}')
"

# No bare excepts, no print()
rtk grep -nE "(^|\s)except:" web/backend/discovery_sync.py
rtk grep -nE "(^|\s)print\(" web/backend/discovery_sync.py | grep -v "^Binary"

# Lint
rtk uv run ruff check web/backend/discovery_sync.py
```

Expect: signature `(int, bool=False) -> tuple[int, list[str]]`, dry_run does not mutate, no bare excepts, no prints, ruff clean.
