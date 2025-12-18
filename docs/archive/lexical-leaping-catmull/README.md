# CSV Import Security & Code Quality Fixes

## Overview

Fix critical security vulnerabilities (SQL injection, path traversal), type safety issues, and code quality problems in the CSV playlist import feature introduced in commit 2073a2e.

**Problem**: The current CSV import implementation has:
- **Security**: SQL injection vulnerability via dynamic query construction
- **Security**: Path traversal risk allowing CSV to reference files outside music library
- **Code Quality**: 220-line monolithic function violating project's ≤20 line standard
- **Type Safety**: Missing type conversions (year, bpm, duration stored as strings)
- **UX**: Errors reported one-at-a-time instead of all upfront

**Solution**:
- Extract 3 helper functions following functional programming principles
- Add security validations (path allowlist, SQL field allowlist)
- Implement two-phase validation (validate all rows → report all errors → import valid ones)
- Apply type conversions during validation for better error messages
- Minor code quality improvements in exporters and commands

## Task Sequence

1. [01-extract-helper-functions.md](./01-extract-helper-functions.md) - Refactor monolithic import_csv() into 3 testable functions
2. [02-add-security-fixes.md](./02-add-security-fixes.md) - Add path traversal and SQL injection protections
3. [03-refactor-import-csv.md](./03-refactor-import-csv.md) - Wire up helpers in main import_csv() function
4. [04-apply-autosolve-fixes.md](./04-apply-autosolve-fixes.md) - Code quality improvements in exporters and commands

## Success Criteria

### Security
- [ ] CSV with paths outside library_root (e.g., `../../etc/passwd`) is rejected
- [ ] CSV with malicious field names (e.g., `"; DROP TABLE tracks--"`) is safely ignored
- [ ] All file paths validated against library_root using `is_relative_to()`
- [ ] All SQL queries use hardcoded field allowlist, not CSV headers

### Code Quality
- [ ] `import_csv()` function reduced from 220 lines to ≤20 lines
- [ ] Three helper functions created, each ≤20 lines (except DB function at ~40)
- [ ] All functions have proper type hints and docstrings
- [ ] Code passes linting: `uv run ruff check src/music_minion/domain/playlists/`
- [ ] Code passes formatting: `uv run ruff format src/music_minion/domain/playlists/`

### Type Safety
- [ ] Year values converted to int during validation
- [ ] BPM values converted to float during validation
- [ ] Duration values converted to float during validation
- [ ] Type conversion errors include row numbers in error messages

### User Experience
- [ ] Two-phase validation: all errors shown upfront before import starts
- [ ] Valid tracks imported even when some rows have errors
- [ ] Error messages include row numbers and specific field issues
- [ ] Single database transaction for all valid tracks (atomic operation)

### Regression Testing
- [ ] All existing CSV import tests pass
- [ ] All existing M3U/M3U8 import tests pass
- [ ] All existing Serato crate import tests pass
- [ ] CSV export functionality unchanged

## Execution Instructions

1. **Execute tasks in numerical order** (01 → 04)
2. Each task file contains:
   - Files to modify/create
   - Implementation details with code examples
   - Acceptance criteria checklist
   - Dependencies on previous tasks
3. **Verify acceptance criteria** before moving to next task
4. **Run tests** after each task:
   ```bash
   uv run ruff check src/music_minion/domain/playlists/
   uv run pytest  # If tests exist
   ```
5. **Test with malicious inputs** after task 02 (security fixes)

## Dependencies

### External Dependencies
- None (uses existing Python stdlib and project dependencies)

### Prerequisites
- Working Music Minion CLI installation
- Commit 2073a2e checked out (CSV import feature exists)
- Python 3.10+ with uv package manager

### Project Standards (from CLAUDE.md)
- **Function length**: ≤20 lines, ≤3 nesting levels
- **Type hints**: Required on all parameters and return values
- **Pure functions**: Prefer functions with explicit state passing over classes
- **Batch operations**: Use `executemany()` for database operations when possible
- **Error handling**: Detailed error messages with location, cause, state

## Testing Strategy

### Security Tests (Create After Task 02)

**Test 1: Path Traversal Attack**
```csv
local_path,title,artist
"../../etc/passwd","Malicious Track","Hacker"
```
Expected: Row rejected with "Path outside library" error

**Test 2: SQL Injection via Field Name**
```csv
local_path,title,"; DROP TABLE tracks--"
"/home/user/Music/test.mp3","Normal Song","Attempt"
```
Expected: Malicious column ignored, track imports with title only

**Test 3: Long Field Values (DoS)**
```csv
local_path,title
"/home/user/Music/test.mp3","A"*1000000
```
Expected: Handle gracefully without crash

### Validation Tests

**Test 4: Invalid Year**
```csv
local_path,title,year
"/home/user/Music/test.mp3","Song","not_a_number"
```
Expected: Error message "Row 2: Year must be a valid integer"

**Test 5: Mixed Valid/Invalid**
```csv
local_path,title,year,bpm
"/home/user/Music/song1.mp3","Good Song","2020","120"
"/home/user/Music/song2.mp3","Bad Year","invalid","130"
"/home/user/Music/song3.mp3","Good Song 2","2021","140"
```
Expected: 2 tracks imported, 1 error message with row 3

### Integration Tests

**Test 6: Complete Import Flow**
- CSV with 10 valid tracks
- Verify playlist created
- Verify all 10 tracks in playlist
- Verify no error messages

**Test 7: Empty CSV**
```csv
local_path,title,artist
```
Expected: Playlist created but empty, no errors

## Implementation Notes

### Two-Phase Validation Approach

The refactored implementation uses a two-phase approach (user's suggestion during review):

**Phase 1: Validate All**
- Parse entire CSV
- Validate each row/field
- Collect ALL error messages
- Build list of valid track data

**Phase 2: Batch Process**
- Create playlist
- Single transaction for all valid tracks
- Insert/update tracks
- Add to playlist

**Benefits**:
- User sees all errors upfront (better UX)
- Enables batch operations (better performance)
- Single atomic transaction (better reliability)
- Cleaner code separation (easier testing)

### SQL Security Pattern

The hardcoded field allowlist pattern is secure because:
1. We iterate `VALID_METADATA_FIELDS` set (hardcoded), NOT CSV headers
2. Malicious field names from CSV are filtered out during validation
3. F-string only contains identifiers from hardcoded allowlist
4. Values still use parameterized queries (`?` placeholders)

This gives us both security AND maintainability (avoid 40 lines of if/elif).

## Performance Considerations

**N+1 Query Decision**:
- Initially identified as performance issue
- Decided against complex `executemany()` batching by field combinations
- Single transaction eliminates most overhead
- Good enough for typical use case (100-1000 tracks)
- Simpler code worth the minor performance trade-off

## Success Metrics

After completion, the CSV import feature will:
- ✅ Be secure against common attack vectors
- ✅ Follow project code standards (≤20 lines per function)
- ✅ Have proper type safety (no string→int/float bugs)
- ✅ Provide better UX (all errors upfront)
- ✅ Be testable (pure functions with clear contracts)
- ✅ Be maintainable (clear separation of concerns)
