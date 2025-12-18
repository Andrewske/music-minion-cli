# Add Security Fixes (Path Traversal & SQL Injection Prevention)

## Files to Modify/Create
- `src/music_minion/domain/playlists/importers.py` (modify - add security validations)

## Implementation Details

Add critical security validations to prevent path traversal and SQL injection attacks via malicious CSV files.

### Security Fix 1: Path Traversal Prevention

**Location**: In `_validate_csv_rows()` function (created in task 01)

**Implementation**:
```python
# After extracting local_path from CSV row
track_path = Path(local_path_str).expanduser().resolve()

# Security check: ensure path is within library_root
if not track_path.is_relative_to(library_root):
    error_messages.append(f"Row {row_num}: Path outside library: {local_path_str}")
    continue  # Skip this row
```

**Why this matters**: Without this check, a malicious CSV could reference files outside the music library like `../../etc/passwd` or `../../../home/user/.ssh/id_rsa`.

**Attack vector prevented**:
- Attacker crafts CSV with paths pointing to sensitive system files
- Import reads metadata from those files
- Potential data exfiltration or system compromise

### Security Fix 2: SQL Injection Prevention

**Location**: In `_upsert_tracks_to_playlist()` function (created in task 01)

**Implementation**:
```python
# Define hardcoded allowlist at module or function level
VALID_METADATA_FIELDS = {
    "title", "artist", "top_level_artist", "album", "genre",
    "year", "duration", "bpm", "key_signature", "remix_artist",
    "soundcloud_id", "spotify_id", "youtube_id", "source"
}

# Build UPDATE query safely - iterate hardcoded set, NOT CSV data
updates = []
values = []
for field in VALID_METADATA_FIELDS:  # Safe: iterate hardcoded set
    if field in track_data:
        updates.append(f"{field} = ?")  # Safe: field name from hardcoded allowlist
        values.append(track_data[field])

if updates:
    query = f"UPDATE tracks SET {', '.join(updates)}, metadata_updated_at = CURRENT_TIMESTAMP WHERE id = ?"
    cursor.execute(query, values + [track_id])
```

**Why this is secure**:
- We iterate `VALID_METADATA_FIELDS` (hardcoded), NOT CSV headers
- Even if CSV contains malicious field names like `"; DROP TABLE tracks--"`, they're filtered out during validation
- The f-string only contains identifiers from our hardcoded allowlist
- Values are still parameterized (the `?` placeholders)

**Attack vector prevented**:
- Attacker crafts CSV with malicious column names
- Without allowlist, dynamic SQL construction could execute arbitrary SQL
- With allowlist, malicious columns are ignored

**Apply same pattern to INSERT**:
```python
# For INSERT operations
fields = [f for f in VALID_METADATA_FIELDS if f in track_data]
placeholders = ["?" for _ in fields]
values = [track_data[f] for f in fields]

insert_query = f"""
    INSERT INTO tracks ({", ".join(fields)}, metadata_updated_at)
    VALUES ({", ".join(placeholders)}, CURRENT_TIMESTAMP)
"""
cursor.execute(insert_query, values)
```

## Acceptance Criteria

- [ ] Path validation check added to `_validate_csv_rows()` using `is_relative_to()`
- [ ] `VALID_METADATA_FIELDS` allowlist defined (at module or function scope)
- [ ] UPDATE query uses allowlist iteration, not CSV input
- [ ] INSERT query uses allowlist iteration, not CSV input
- [ ] Test case: CSV with `../../etc/passwd` path is rejected
- [ ] Test case: CSV with malicious field name `"; DROP TABLE tracks--"` is safely ignored
- [ ] No regressions: valid CSVs still import correctly

## Dependencies

- Task 01 must be complete (helper functions extracted)

## Security Testing

Create test CSV files to verify protections:

**Test 1: Path traversal**
```csv
local_path,title,artist
"../../etc/passwd","Malicious","Hacker"
```
Expected: Row rejected with error "Path outside library"

**Test 2: SQL injection attempt**
```csv
local_path,title,"; DROP TABLE tracks--"
"/home/user/Music/test.mp3","Normal Song","123"
```
Expected: Malicious column ignored, track imports with title/artist only

**Test 3: Long field values (DoS attempt)**
```csv
local_path,title
"/home/user/Music/test.mp3","A"*1000000
```
Expected: Should handle gracefully (SQLite has limits, but shouldn't crash)
