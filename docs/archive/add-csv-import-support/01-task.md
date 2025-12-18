## Files to Modify/Create

- `src/music_minion/domain/playlists/importers.py`: Add CSV import functions and update format detection
- `src/music_minion/commands/playlist.py`: Update import command help text to mention CSV support

## Implementation Details

Created CSV import functionality that:
- Parses CSV files with proper validation of metadata fields using csv.Sniffer for dialect detection
- Validates CSV format requires headers in first row and local_path column
- Updates existing track metadata in database by matching local_path, or creates new tracks
- Handles CSV parsing errors, missing files, invalid data types
- Provides detailed error reporting for validation failures
- Supports standard CSV format with quoted fields and escaped commas

## Acceptance Criteria

- [x] CSV files with headers are properly parsed
- [x] CSV files without headers are rejected with clear error
- [x] Metadata fields are validated against database schema
- [x] Invalid data types (non-numeric year/bpm) are reported as errors
- [x] Tracks are matched by local_path for metadata updates
- [x] New tracks can be created if local_path doesn't exist
- [x] Import returns proper statistics (tracks updated, created, errors)
- [x] Error handling for malformed CSV files
- [x] Support for common CSV variations (quoted fields, escaped commas)

## Dependencies

- Existing database schema and CRUD functions
- CSV export format as reference for expected columns