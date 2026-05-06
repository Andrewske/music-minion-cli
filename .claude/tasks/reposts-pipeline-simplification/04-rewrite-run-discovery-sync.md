---
task: 04-rewrite-run-discovery-sync
status: pending
depends: [01-add-repost-candidates-query, 02-rewrite-prepare-for-sync, 03-extend-sync-log-telemetry]
files:
  - path: web/backend/discovery_sync.py
    action: modify
---

# Slim `run_discovery_sync` to DB-Only + Deep + Mixes

## Context

Replace the multi-step pipeline (fetch reposts from SC, filter, duration-split, slot-cap, chronological select, backfill) with three `get_repost_candidates` calls (reposts + deep + mixes), the per-artist cap helper, and a single SC push each. All three playlists now use the same DB-driven primitive — TODO D dissolves into this PR. Adds new helper `_sync_candidates_to_local_db`. Caller of all soon-to-be-deleted helpers — Step 5 cleans up.

## Files to Modify/Create

- `web/backend/discovery_sync.py` (modify) — rewrite `run_discovery_sync`, add `_sync_candidates_to_local_db`

## Implementation Details

Replace existing `run_discovery_sync` (currently `discovery_sync.py:478`):

```python
def run_discovery_sync(
    dry_run: bool = False,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> DiscoverySyncResult:
    started_at = datetime.now(timezone.utc)
    errors: list[str] = []

    state = get_web_provider_state()
    if state is None:
        raise RuntimeError("SoundCloud not authenticated")

    reposts_playlist_id = discovery_queries.get_discovery_playlist_id("soundcloud_reposts")
    if reposts_playlist_id is None:
        raise RuntimeError("No discovery playlist configured")
    sc_reposts_playlist_id = _get_sc_playlist_id(reposts_playlist_id)

    target_count, kept_sc_ids = prepare_for_sync(reposts_playlist_id, dry_run=dry_run)

    # --- Reposts (short tracks, recent) ---
    candidates: list[dict] = []
    if target_count > 0:
        if progress_callback:
            progress_callback("Picking candidates...", 0, 1)
        pool = discovery_queries.get_repost_candidates(
            exclude_playlist_id=reposts_playlist_id,
            exclude_sc_ids=set(kept_sc_ids),
            limit=target_count * 3,  # headroom for cap
        )
        candidates = discovery_queries.apply_per_artist_cap(pool, target=target_count)

    fresh_sc_ids = [c["soundcloud_id"] for c in candidates]
    if not dry_run:
        if candidates:
            _sync_candidates_to_local_db(
                candidates, reposts_playlist_id, position_offset=len(kept_sc_ids)
            )
        full_sc_ids = kept_sc_ids + fresh_sc_ids
        if full_sc_ids and sc_reposts_playlist_id:
            state, success, err = _push_to_sc_playlist(
                state, sc_reposts_playlist_id, full_sc_ids, replace=True
            )
            if not success:
                errors.append(f"SC reposts push failed: {err}")

    # --- Deep (short tracks, 7–90d window) ---
    deep_playlist_id = discovery_queries.get_discovery_playlist_id("soundcloud_reposts_deep")
    deep_candidates: list[dict] = []
    if deep_playlist_id and not dry_run:
        deep_pool = discovery_queries.get_repost_candidates(
            exclude_playlist_id=deep_playlist_id,
            exclude_sc_ids=set(),
            window_days_min=7,
            window_days_max=90,
            limit=300,
        )
        deep_candidates = discovery_queries.apply_per_artist_cap(deep_pool, target=100)
        sc_deep_id = _get_sc_playlist_id(deep_playlist_id)
        if deep_candidates and sc_deep_id:
            _sync_candidates_to_local_db(deep_candidates, deep_playlist_id, position_offset=0)
            deep_sc_ids = [c["soundcloud_id"] for c in deep_candidates]
            state, success, err = _push_to_sc_playlist(
                state, sc_deep_id, deep_sc_ids, replace=True
            )
            if not success:
                errors.append(f"SC deep push failed: {err}")

    # --- Mixes (long tracks, any window) ---
    mixes_playlist_id = discovery_queries.get_mixes_playlist_id()
    mixes_candidates: list[dict] = []
    if mixes_playlist_id and not dry_run:
        mixes_pool = discovery_queries.get_repost_candidates(
            exclude_playlist_id=mixes_playlist_id,
            exclude_sc_ids=set(),
            duration_min_ms=600_000,
            duration_max_ms=7_200_000,
            limit=60,
        )
        mixes_candidates = discovery_queries.apply_per_artist_cap(mixes_pool, target=20)
        sc_mixes_id = _get_sc_playlist_id(mixes_playlist_id)
        if mixes_candidates and sc_mixes_id:
            _sync_candidates_to_local_db(mixes_candidates, mixes_playlist_id, position_offset=0)
            mixes_sc_ids = [c["soundcloud_id"] for c in mixes_candidates]
            state, success, err = _push_to_sc_playlist(
                state, sc_mixes_id, mixes_sc_ids, replace=True
            )
            if not success:
                errors.append(f"SC mixes push failed: {err}")

    log_sync_run(
        started_at=started_at,
        candidates_returned=len(candidates),
        deep_candidates_returned=len(deep_candidates),
        kept=len(kept_sc_ids),
        tracks_added=len(fresh_sc_ids),
        mixes_added=len(mixes_candidates),
        errors=errors,
        dry_run=dry_run,
        duration_seconds=(datetime.now(timezone.utc) - started_at).total_seconds(),
    )

    return DiscoverySyncResult(
        tracks_fetched=0,
        tracks_new=0,
        tracks_added_to_playlist=len(fresh_sc_ids),
        mixes_added=len(mixes_candidates),
        artists_checked=0,
        errors=errors,
        dry_run=dry_run,
    )
```

Add `_sync_candidates_to_local_db` (new helper, replaces a chunk of the old pipeline):

```python
def _sync_candidates_to_local_db(
    candidates: list[dict],
    playlist_id: int,
    position_offset: int,
) -> None:
    """INSERT into tracks (if missing) and playlist_tracks. No status writes."""
    with get_db_connection() as conn:
        for i, c in enumerate(candidates):
            conn.execute(
                """INSERT OR IGNORE INTO tracks
                       (soundcloud_id, title, artist_name, duration_ms, source)
                   VALUES (?, ?, ?, ?, 'soundcloud')""",
                (c["soundcloud_id"], c["title"], c["artist_name"], c["duration_ms"]),
            )
            row = conn.execute(
                "SELECT id FROM tracks WHERE soundcloud_id = ?",
                (c["soundcloud_id"],),
            ).fetchone()
            track_id = row["id"]
            conn.execute(
                "INSERT INTO playlist_tracks (playlist_id, track_id, position) VALUES (?, ?, ?)",
                (playlist_id, track_id, position_offset + i),
            )
        conn.execute(
            """UPDATE playlists SET track_count = (
                SELECT COUNT(*) FROM playlist_tracks WHERE playlist_id = ?
            ) WHERE id = ?""",
            (playlist_id, playlist_id),
        )
        conn.commit()
```

`source='soundcloud'` per CLAUDE.md ownership invariant. **Do NOT touch `discovery_tracks.status`** (decision #13).

## Verification

```bash
# Dry run end-to-end (no SC push, no DB writes — verify with playlist row count)
uv run python -c "
import sqlite3
from pathlib import Path
db = Path.home() / '.local/share/music-minion/music_minion.db'
con = sqlite3.connect(db); con.row_factory = sqlite3.Row
before = con.execute('SELECT COUNT(*) AS n FROM playlist_tracks WHERE playlist_id = 26').fetchone()['n']
from web.backend.discovery_sync import run_discovery_sync
r = run_discovery_sync(dry_run=True)
after = con.execute('SELECT COUNT(*) AS n FROM playlist_tracks WHERE playlist_id = 26').fetchone()['n']
assert before == after, f'dry_run mutated playlist_tracks: {before} -> {after}'
print('errors:', r.errors)
print('tracks_added_to_playlist:', r.tracks_added_to_playlist)
"

# Lint
rtk uv run ruff check web/backend/discovery_sync.py
```

Expect: no errors, `tracks_added_to_playlist` is 0 in dry_run, `playlist_tracks` row count unchanged. Wet run gated to Step 7 (deploy).
