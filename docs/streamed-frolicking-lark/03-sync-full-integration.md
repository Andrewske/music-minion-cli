# Sync Full Integration

## Files to Modify/Create
- `src/music_minion/domain/sync/engine.py` (modify)
- `src/music_minion/domain/sync/__init__.py` (modify)
- `src/music_minion/commands/sync.py` (modify)

## Implementation Details

Integrate ELO export into the `sync full` command.

### 3.1 Add import to engine.py
```python
from music_minion.domain.library.metadata import write_elo_to_file
```

### 3.2 Add `sync_elo_export()` function to engine.py
```python
def sync_elo_export(
    track_ids: Optional[list[int]] = None,
    show_progress: bool = True,
) -> dict[str, int]:
    """Export global ELO ratings to file metadata.

    Writes GLOBAL_ELO tag to audio files for tracks that have been rated.
    Skips tracks with default ELO (1500) to avoid cluttering unrated tracks.

    Args:
        track_ids: Optional list of specific track IDs to export (None = all rated tracks)
        show_progress: Whether to print progress messages

    Returns:
        Dictionary with stats: {'success': count, 'failed': count, 'skipped': count}
    """
```

Query logic:
- Get tracks with `rating != 1500.0 AND comparison_count > 0`
- Call `write_elo_to_file(global_elo=rating, update_comment=False)`
- Return `{success, failed, skipped}` stats
- Use milestone-based progress (25%, 50%, 75%, 100%)

### 3.3 Export in `__init__.py`
Add `sync_elo_export` to the exports in `src/music_minion/domain/sync/__init__.py`:
- Add to import statement
- Add to `__all__` list

### 3.4 Integrate into `_sync_local_full()` in sync.py
Add after line 148 (after metadata export, before reload):
```python
# Phase 3: Export ELO ratings to files
log("Exporting ELO ratings to files...", level="info")
elo_result = sync.sync_elo_export(show_progress=True)
log(f"✓ Exported ELO to {elo_result.get('success', 0)} files", level="info")
```

## Acceptance Criteria
- [ ] `sync full` command writes GLOBAL_ELO to rated tracks
- [ ] Unrated tracks (ELO=1500) are skipped
- [ ] Progress is displayed during export
- [ ] Stats are logged on completion

## Dependencies
- Task 01: Core ELO functions must be implemented first
