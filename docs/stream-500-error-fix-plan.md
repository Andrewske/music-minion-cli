# 500 Internal Server Error Analysis: /api/tracks/{id}/stream

## Root Cause Analysis

The 500 error occurs when WaveSurfer attempts to load audio from `/api/tracks/11812/stream`. Analysis reveals multiple defensive programming gaps:

### Primary Issues Identified

1. **NULL local_path Handling**: Database query returns `row["local_path"]` which may be `None`, causing `Path(None)` to fail
2. **Invalid Path Creation**: No validation that `local_path` is a valid string before `Path(row["local_path"])`
3. **File Existence Check**: Path existence check happens after Path creation, but invalid paths crash earlier
4. **MIME Type Detection**: Assumes file extension exists for MIME detection, but invalid paths have no `.suffix`
5. **Frontend Error Handling**: WaveSurfer receives 500 error but frontend doesn't handle streaming failures gracefully

### Code Flow Analysis

```
Frontend: useWavesurfer.ts:46 → getStreamUrl(trackId) → "/api/tracks/11812/stream"
Backend: tracks.py:28 → Path(row["local_path"]) ← CRASHES if local_path is None
```

## Comprehensive Fix Plan

### Phase 1: Backend Defensive Programming

#### 1.1 Enhanced Database Query Validation
```python
# In tracks.py stream_audio() and get_waveform()
if row is None:
    raise HTTPException(status_code=404, detail="Track not found")

local_path = row["local_path"]
if not local_path or not isinstance(local_path, str):
    logger.error(f"Track {track_id} has invalid local_path: {local_path!r}")
    raise HTTPException(status_code=410, detail="Track file path unavailable")

file_path = Path(local_path)
```

#### 1.2 Safe Path Operations
```python
try:
    file_path = Path(local_path).resolve()  # Resolve to absolute path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Audio file not found: {file_path}")
except (OSError, ValueError) as e:
    logger.error(f"Invalid file path for track {track_id}: {local_path} - {e}")
    raise HTTPException(status_code=410, detail="Invalid track file path")
```

#### 1.3 Robust MIME Type Detection
```python
def get_audio_mime_type(file_path: Path) -> str:
    """Safely detect MIME type for audio files."""
    if not file_path.suffix:
        return "application/octet-stream"
    
    suffix = file_path.suffix.lower()
    mime_map = {
        ".opus": "audio/opus",
        ".mp3": "audio/mpeg", 
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".wav": "audio/wav"
    }
    
    mime_type = mime_map.get(suffix)
    if mime_type:
        return mime_type
        
    # Fallback to mimetypes
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type or "application/octet-stream"
```

### Phase 2: Frontend Error Handling

#### 2.1 Enhanced WaveSurfer Error Handling
```typescript
// In useWavesurfer.ts
wavesurfer.on('error', (error) => {
  console.error('WaveSurfer error:', error);
  setError('Audio playback failed. File may be missing or corrupted.');
});

wavesurfer.on('loading', (percent) => {
  // Show loading progress
  setLoadingProgress(percent);
});
```

#### 2.2 Stream URL Validation
```typescript
// Add stream availability check
export async function checkStreamAvailable(trackId: number): Promise<boolean> {
  try {
    const response = await fetch(`/api/tracks/${trackId}/stream`, { method: 'HEAD' });
    return response.ok;
  } catch {
    return false;
  }
}

// Use in useWavesurfer before loading
const isAvailable = await checkStreamAvailable(trackId);
if (!isAvailable) {
  setError('Audio file is not available for streaming');
  return;
}
```

### Phase 3: Database Integrity Checks

#### 3.1 Add Data Validation Function
```python
def validate_track_data_integrity(db_path: str) -> list[dict]:
    """Check for tracks with invalid local_path values."""
    issues = []
    
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT id, title, artist, local_path, source
            FROM tracks 
            WHERE local_path IS NULL 
               OR local_path = ''
               OR (local_path IS NOT NULL AND local_path != '')
        """)
        
        for row in cursor:
            track_id = row['id']
            local_path = row['local_path']
            
            if local_path is None:
                issues.append({
                    'track_id': track_id,
                    'issue': 'NULL local_path',
                    'title': row['title']
                })
            elif not isinstance(local_path, str) or not local_path.strip():
                issues.append({
                    'track_id': track_id, 
                    'issue': 'Empty local_path',
                    'title': row['title']
                })
            else:
                file_path = Path(local_path)
                if not file_path.exists():
                    issues.append({
                        'track_id': track_id,
                        'issue': 'File not found',
                        'path': str(file_path),
                        'title': row['title']
                    })
    
    return issues
```

#### 3.2 Add CLI Command for Data Integrity
```python
# In commands/admin.py
@admin.command()
def check_track_integrity():
    """Check for tracks with missing or invalid local_path values."""
    issues = validate_track_data_integrity(get_db_path())
    
    if not issues:
        log("✅ All tracks have valid local_path values")
        return
    
    log(f"⚠️  Found {len(issues)} tracks with issues:")
    for issue in issues:
        log(f"  Track {issue['track_id']}: {issue['issue']} - {issue['title']}")
```

### Phase 4: Testing Strategy

#### 4.1 Unit Tests for Edge Cases
```python
# In web/backend/tests/test_tracks.py
def test_stream_track_with_null_path(client):
    """Test streaming track with NULL local_path."""
    # Insert test track with NULL local_path
    with get_db_connection() as conn:
        conn.execute("INSERT INTO tracks (id, title, local_path) VALUES (99999, 'Test', NULL)")
    
    response = client.get("/api/tracks/99999/stream")
    assert response.status_code == 410
    assert "unavailable" in response.json()["detail"]

def test_stream_track_with_invalid_path(client):
    """Test streaming track with invalid local_path."""
    with get_db_connection() as conn:
        conn.execute("INSERT INTO tracks (id, title, local_path) VALUES (99998, 'Test', '/invalid/path')")
    
    response = client.get("/api/tracks/99998/stream") 
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
```

#### 4.2 Integration Tests
```python
def test_full_streaming_workflow(client):
    """Test complete streaming workflow with valid track."""
    # Create temp audio file
    temp_file = create_temp_audio_file()
    
    # Insert track with valid path
    with get_db_connection() as conn:
        conn.execute("INSERT INTO tracks (title, local_path) VALUES (?, ?)", 
                    ("Test Track", str(temp_file)))
        track_id = conn.lastrowid
    
    # Test stream endpoint
    response = client.get(f"/api/tracks/{track_id}/stream")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/")
    
    # Cleanup
    temp_file.unlink()
```

### Phase 5: Prevention Measures

#### 5.1 Database Constraints
```sql
-- Add check constraint to prevent NULL local_path for local tracks
ALTER TABLE tracks ADD CONSTRAINT check_local_path 
    CHECK (source != 'local' OR local_path IS NOT NULL);
```

#### 5.2 Import Validation
```python
# In import_tracks.py
def validate_track_before_import(track: dict) -> bool:
    """Validate track data before database insertion."""
    if track.get('source') == 'local':
        local_path = track.get('local_path')
        if not local_path or not Path(local_path).exists():
            logger.warning(f"Skipping track with invalid local_path: {local_path}")
            return False
    return True
```

#### 5.3 Monitoring and Alerts
```python
# Add to admin command
@admin.command() 
def monitor_stream_errors():
    """Monitor recent streaming errors and alert if threshold exceeded."""
    # Check logs for 500 errors in last hour
    # Send notification if > 5% of requests fail
    pass
```

## Implementation Priority

1. **HIGH**: Fix NULL local_path crash in backend (Phase 1.1)
2. **HIGH**: Add safe Path operations (Phase 1.2) 
3. **MEDIUM**: Frontend error handling (Phase 2)
4. **MEDIUM**: Data integrity checks (Phase 3)
5. **LOW**: Enhanced testing (Phase 4)
6. **LOW**: Prevention measures (Phase 5)

## Expected Outcomes

- **Immediate**: 500 errors eliminated for tracks with NULL/invalid local_path
- **Short-term**: Clear error messages guide users to fix data issues  
- **Long-term**: Robust streaming with comprehensive error handling and data validation</content>
<parameter name="filePath">docs/stream-500-error-fix-plan.md