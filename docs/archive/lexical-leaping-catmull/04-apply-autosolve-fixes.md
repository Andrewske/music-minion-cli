# Apply Autosolve Fixes (Code Quality & Documentation)

## Files to Modify/Create
- `src/music_minion/domain/playlists/exporters.py` (modify)
- `src/music_minion/commands/playlist.py` (modify)

## Implementation Details

Apply five straightforward code quality improvements identified during code review.

### Fix 1: Move Import Statement Out of Loop

**File**: `src/music_minion/domain/playlists/exporters.py`
**Location**: Lines 145-146 (inside `export_serato_crate` function)

**Current code**:
```python
for track in tracks:
    track_path = Path(track["local_path"])
    from pyserato.model.track import Track  # ← Inside loop!

    serato_track = Track(path=track_path.absolute())
    crate.add_track(serato_track)
```

**Fixed code**:
```python
from pyserato.model.track import Track

for track in tracks:
    track_path = Path(track["local_path"])
    serato_track = Track(path=track_path.absolute())
    crate.add_track(serato_track)
```

Move the import to the top of the `export_serato_crate()` function (after the existing `from pyserato.model.crate import Crate` and `from pyserato.builder import Builder` imports around line 119-120).

### Fix 2: Simplify Type Conversion

**File**: `src/music_minion/domain/playlists/exporters.py`
**Location**: Lines 229-234 (inside `export_csv` function)

**Current code**:
```python
if value is None:
    row[field] = ""
elif isinstance(value, (int, float)):
    row[field] = str(value)
else:
    row[field] = str(value)
```

**Fixed code**:
```python
row[field] = "" if value is None else str(value)
```

This is cleaner and removes the redundant `elif/else` branches.

### Fix 3: Add CSV Export NULL Documentation

**File**: `src/music_minion/domain/playlists/exporters.py`
**Location**: Line 163 docstring of `export_csv()` function

**Add to docstring**:
```python
def export_csv(
    playlist_id: int,
    output_path: Path,
) -> int:
    """
    Export a playlist to CSV format with all track metadata including database ID.

    Note: NULL values are exported as empty strings for CSV compatibility.

    Args:
        playlist_id: ID of the playlist to export
        output_path: Path where CSV file should be written

    Returns:
        Number of tracks exported

    Raises:
        ValueError: If playlist doesn't exist or is empty
    """
```

### Fix 4: Extract Constant for Format Strings

**File**: `src/music_minion/commands/playlist.py`
**Location**: Top of file (after imports, before function definitions)

**Add constant**:
```python
# Supported playlist import/export formats
SUPPORTED_IMPORT_FORMATS = ".m3u, .m3u8, .crate, .csv"
```

**Replace usages** (lines 955, 977, 1053):

Line 955:
```python
# OLD
log("Supported formats: .m3u, .m3u8, .crate, .csv", level="info")

# NEW
log(f"Supported formats: {SUPPORTED_IMPORT_FORMATS}", level="info")
```

Line 977:
```python
# OLD
log("Supported formats: .m3u, .m3u8, .crate, .csv", level="info")

# NEW
log(f"Supported formats: {SUPPORTED_IMPORT_FORMATS}", level="info")
```

Line 1053:
```python
# OLD
log("Formats: m3u8 (default), crate, csv, all", level="info")

# NEW
# Note: This one is slightly different (shows defaults), keep as-is or update to:
log("Formats: m3u8 (default), crate, csv, all", level="info")
```

Actually, line 1053 has different wording ("Formats" vs "Supported formats" and includes "all"), so keep it as-is to avoid changing behavior.

**Updated**: Only replace lines 955 and 977.

### Fix 5: Add Type Annotation to validate_csv_metadata_field()

**File**: `src/music_minion/domain/playlists/importers.py`
**Location**: Function signature around line 311

**Current**:
```python
def validate_csv_metadata_field(
    field_name: str, value: str
) -> tuple[bool, Optional[str]]:
```

This is already correct! No change needed (type annotation already present).

**Update**: This fix is already complete in the current code.

## Acceptance Criteria

- [ ] Import statement moved out of loop in `exporters.py`
- [ ] Type conversion simplified to one-liner in `exporters.py`
- [ ] CSV export docstring updated with NULL handling note
- [ ] `SUPPORTED_IMPORT_FORMATS` constant added to `commands/playlist.py`
- [ ] String literals replaced with constant at lines 955 and 977
- [ ] Code passes linting: `uv run ruff check src/music_minion/domain/playlists/`
- [ ] Code passes formatting: `uv run ruff format src/music_minion/domain/playlists/`
- [ ] All existing tests still pass

## Dependencies

None - these are independent code quality fixes

## Testing

- Run existing test suite to ensure no regressions
- Verify import/export functionality unchanged
- Check that error messages still display correct format strings

## Notes

These are low-risk, high-value improvements:
- Performance: Import statement no longer executed N times
- Readability: Type conversion is clearer
- Documentation: NULL handling is now explicit
- Maintainability: Format string defined once (DRY principle)
