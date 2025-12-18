# Extract Helper Functions for CSV Import

## Files to Modify/Create
- `src/music_minion/domain/playlists/importers.py` (modify - extract 3 new functions)

## Implementation Details

Extract three helper functions from the monolithic `import_csv()` function (currently 220 lines) to meet the ≤20 line project standard.

### Function 1: `_parse_csv_file(local_path: Path) -> tuple[csv.DictReader, dict]`

**Purpose**: Handle CSV file reading and dialect detection

**Implementation**:
- Read CSV file with UTF-8 encoding
- Use `csv.Sniffer` to detect dialect (delimiter detection for comma/tab/semicolon)
- Use `csv.Sniffer.has_header()` to verify headers exist
- Validate required field `local_path` is present in headers
- Return DictReader and metadata dict (for future extensibility)
- Raise `ValueError` if:
  - File has no headers
  - Required `local_path` column missing
  - CSV is empty/malformed

**Expected length**: ~15-20 lines

### Function 2: `_validate_csv_rows(reader: csv.DictReader, library_root: Path, valid_fields: set[str]) -> tuple[list[dict], list[str]]`

**Purpose**: Parse and validate all CSV rows (two-phase validation approach)

**Implementation**:
- Iterate all rows in CSV
- For each row:
  - Extract `local_path`, validate not empty
  - Validate path exists as file (after expanduser/resolve)
  - **Security**: Validate path is within library_root (see task 02)
  - For each metadata field:
    - Skip if not in `valid_fields` set
    - Call `validate_csv_metadata_field()` for validation
    - **Convert types immediately**: year→int, duration/bpm→float
    - Collect validation errors with row numbers
  - If row has valid local_path, add to valid_tracks_data list
- Return (valid_tracks_data, error_messages)

**Key principle**: All-or-nothing per row - if ANY field fails validation, skip entire row

**Expected length**: ~20 lines

### Function 3: `_upsert_tracks_to_playlist(playlist_id: int, tracks_data: list[dict]) -> tuple[int, int]`

**Purpose**: Database operations - insert/update tracks and add to playlist

**Implementation**:
- Wrap ALL operations in single transaction (using `with get_db_connection()`)
- For each valid track in tracks_data:
  - Query: `SELECT id FROM tracks WHERE local_path = ?`
  - If exists (UPDATE path):
    - Build UPDATE with hardcoded field allowlist (see task 02 for security)
    - Execute UPDATE with parameterized values
  - If not exists (INSERT path):
    - Build INSERT with fields from track_data
    - Execute INSERT with parameterized values
  - Get track_id (from existing or `cursor.lastrowid`)
  - Call `add_track_to_playlist(playlist_id, track_id)`
  - Track counts: tracks_added, duplicates_skipped
- Return (tracks_added, duplicates_skipped)

**Expected length**: ~40 lines (acceptable for DB operations with two code paths)

### Additional Changes

**Update `validate_csv_metadata_field()` function**:
- Add explicit return type annotation: `-> tuple[bool, Optional[str]]`
- Keep as validation-only (no conversion) - cleaner separation of concerns
- Type conversion happens in `_validate_csv_rows()` after validation passes

## Acceptance Criteria

- [ ] Three new private functions created with leading underscore
- [ ] Each function ≤20 lines (except `_upsert_tracks_to_playlist` at ~40 lines for DB logic)
- [ ] All functions have proper type hints on parameters and return values
- [ ] Docstrings added explaining purpose, args, returns, and raises
- [ ] `validate_csv_metadata_field()` has explicit return type annotation
- [ ] Functions are pure/testable (no global state dependencies)
- [ ] Code compiles without errors (run `uv run ruff check src/music_minion/domain/playlists/importers.py`)

## Dependencies

None - this is the foundational refactoring task

## Notes

- Don't wire up these functions yet - that happens in task 03
- Focus on extraction and getting the interfaces correct
- The old `import_csv()` function will be refactored in task 03 to use these helpers
