# Playlist Export Integration

## Files to Modify/Create
- `src/music_minion/domain/playlists/exporters.py` (modify)

## Implementation Details

Add `--sync-metadata` flag to playlist export that writes PLAYLIST_ELO and updates COMMENT.

### 2.1 Add import
```python
from music_minion.domain.library.metadata import write_elo_to_file
```

### 2.2 Modify `export_playlist()` signature (around line 240)
```python
def export_playlist(
    playlist_id: Optional[int] = None,
    playlist_name: Optional[str] = None,
    format_type: str = "m3u8",
    output_path: Optional[Path] = None,
    library_root: Optional[Path] = None,
    use_relative_paths: bool = True,
    sync_metadata: bool = False,  # NEW PARAMETER
) -> tuple[Path, int]:
```

### 2.3 Add metadata sync logic (before return, around line 316)
```python
# Sync ELO metadata to files if requested
if sync_metadata:
    from loguru import logger
    tracks = get_playlist_tracks(pl["id"])
    elo_success = 0
    elo_failed = 0

    for track in tracks:
        local_path = track.get("local_path")
        playlist_elo = track.get("playlist_elo_rating")

        # Skip tracks without local files or ELO ratings
        if not local_path or not os.path.exists(local_path):
            continue
        if playlist_elo is None or playlist_elo == 1500.0:
            continue

        success = write_elo_to_file(
            local_path=local_path,
            playlist_elo=playlist_elo,
            update_comment=True,  # Prepend to COMMENT for DJ software sorting
        )

        if success:
            elo_success += 1
        else:
            elo_failed += 1

    if elo_success > 0 or elo_failed > 0:
        logger.info(f"ELO metadata sync: {elo_success} succeeded, {elo_failed} failed")
```

### 2.4 Update `auto_export_playlist()` to pass through `sync_metadata`
Update the function signature:
```python
def auto_export_playlist(
    playlist_id: int,
    export_formats: list[str],
    library_root: Path,
    use_relative_paths: bool = True,
    sync_metadata: bool = False,  # NEW PARAMETER
) -> list[tuple[str, Path, int]]:
```

Pass through in the internal call:
```python
output_path, tracks_exported = export_playlist(
    playlist_id=playlist_id,
    format_type=format_type,
    library_root=library_root,
    use_relative_paths=use_relative_paths,
    sync_metadata=sync_metadata,  # Pass through
)
```

## Acceptance Criteria
- [ ] `export playlist <name> --sync-metadata` writes PLAYLIST_ELO to files
- [ ] COMMENT field is prepended with zero-padded ELO (e.g., `1532 - existing comment`)
- [ ] Unrated tracks (ELO=1500) are skipped
- [ ] Stats are logged on completion
- [ ] Works with all export formats (m3u8, crate, csv)

## Dependencies
- Task 01: Core ELO functions must be implemented first
