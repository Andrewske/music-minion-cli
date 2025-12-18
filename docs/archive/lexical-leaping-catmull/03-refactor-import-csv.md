# Refactor import_csv() Function to Use New Helpers

## Files to Modify/Create
- `src/music_minion/domain/playlists/importers.py` (modify - refactor main function)
- `src/music_minion/domain/playlists/importers.py` (modify - update import_playlist caller)

## Implementation Details

Refactor the monolithic `import_csv()` function (currently 220 lines) to use the new helper functions, reducing it to ~15-20 lines.

### Refactor `import_csv()` function

**New signature**:
```python
def import_csv(
    local_path: Path,
    playlist_name: str,
    library_root: Path,  # NEW parameter (security requirement)
    description: Optional[str] = None,
) -> tuple[int, int, int, list[str]]:
```

**New implementation flow**:
```python
def import_csv(
    local_path: Path,
    playlist_name: str,
    library_root: Path,
    description: Optional[str] = None,
) -> tuple[int, int, int, list[str]]:
    """
    Import a CSV playlist file with track metadata.

    Two-phase approach:
    1. Parse and validate entire CSV (collect all errors)
    2. Batch process all valid tracks in single transaction

    Args:
        local_path: Path to the CSV file
        playlist_name: Name for the imported playlist
        library_root: Root directory of music library (for path validation)
        description: Optional description for the playlist

    Returns:
        Tuple of (playlist_id, tracks_added, duplicates_skipped, error_messages)

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV format is invalid
    """
    if not local_path.exists():
        raise FileNotFoundError(f"CSV file not found: {local_path}")

    # Phase 1: Parse and validate
    reader, metadata = _parse_csv_file(local_path)

    valid_metadata_fields = {
        "title", "artist", "top_level_artist", "album", "genre",
        "year", "duration", "bpm", "key_signature", "remix_artist",
        "soundcloud_id", "spotify_id", "youtube_id", "source",
    }

    valid_tracks_data, error_messages = _validate_csv_rows(
        reader, library_root, valid_metadata_fields
    )

    # Create playlist
    playlist_id = create_playlist(
        name=playlist_name,
        playlist_type="manual",
        description=description or f"Imported from {local_path.name}",
    )

    # Phase 2: Batch process valid tracks
    if valid_tracks_data:
        tracks_added, duplicates_skipped = _upsert_tracks_to_playlist(
            playlist_id, valid_tracks_data
        )
    else:
        tracks_added, duplicates_skipped = 0, 0

    return playlist_id, tracks_added, duplicates_skipped, error_messages
```

**Expected length**: 15-20 lines (excluding docstring)

### Update `import_playlist()` function

**Location**: Same file, around line 842

**Change**:
```python
# OLD
elif format_type == "csv":
    return import_csv(local_path, playlist_name, description)

# NEW
elif format_type == "csv":
    return import_csv(local_path, playlist_name, library_root, description)
```

This passes the `library_root` parameter to enable path validation.

## Acceptance Criteria

- [ ] `import_csv()` function reduced to ≤20 lines (excluding docstring)
- [ ] New `library_root` parameter added to signature
- [ ] Function calls three helper functions in correct order
- [ ] Two-phase approach implemented (validate all, then process valid)
- [ ] `import_playlist()` updated to pass `library_root` to `import_csv()`
- [ ] All existing CSV import tests still pass
- [ ] Function has comprehensive docstring explaining two-phase approach
- [ ] Error handling preserved (FileNotFoundError, ValueError)

## Dependencies

- Task 01 must be complete (helper functions extracted)
- Task 02 must be complete (security fixes in helpers)

## Testing

**Test the complete refactored flow**:

1. **Valid CSV import**:
   - Create CSV with 5 valid tracks
   - Verify all 5 tracks imported
   - Verify playlist created
   - Verify no error messages

2. **Mixed valid/invalid CSV**:
   - Create CSV with 3 valid + 2 invalid rows (bad year, missing path)
   - Verify 3 valid tracks imported
   - Verify 2 error messages returned
   - Verify error messages include row numbers

3. **All invalid CSV**:
   - Create CSV with only invalid rows
   - Verify playlist created but empty (tracks_added = 0)
   - Verify all error messages returned

4. **Path traversal attack**:
   - Create CSV with `../../etc/passwd`
   - Verify track rejected
   - Verify error message includes "Path outside library"

## Notes

- The old 220-line function should be completely replaced
- All logic now delegated to the three helper functions
- Main function is just orchestration: parse → validate → create playlist → upsert
- This makes testing much easier (can unit test each helper independently)
