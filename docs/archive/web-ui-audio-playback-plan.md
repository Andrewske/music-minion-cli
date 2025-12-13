# Web UI Audio Playback Implementation Plan

## Overview
Fix audio playback in the Music Minion web UI by implementing two critical backend endpoints (`/stream` and `/waveform`) that currently return 501 errors. Implement progressive enhancement where audio streaming works independently of waveform visualization—if waveform generation fails, audio still plays.

## Architecture Decisions

### Decision 1: Progressive Enhancement Strategy
**Choice**: Audio streaming works independently of waveform visualization
**Rationale**: Better UX—users can always play audio even if waveform generation fails (e.g., `audiowaveform` CLI missing). Frontend gracefully degrades to basic playback without visualization.

### Decision 2: Error Handling Philosophy
**Choice**: Fail-fast on audio streaming, graceful degradation on waveform
**Rationale**: Audio is critical path; waveform is enhancement. Waveform failures don't show user-facing errors, just skip visualization. Audio failures show clear error with retry button.

### Decision 3: Waveform Generation with pydub
**Choice**: Use pydub (pure Python) instead of audiowaveform CLI
**Rationale**: No external CLI dependency, simpler error handling, already in project dependencies. Generate ~1000 peaks by downsampling audio data (min/max per chunk).

### Decision 4: Waveform Caching
**Choice**: Cache waveform JSON to disk at `~/.local/share/music-minion/waveforms/{track_id}.json`
**Rationale**: Waveform generation is expensive (~1 second per track). Cache enables instant loading on subsequent plays. No cache eviction needed (personal project).

### Decision 5: MIME Type Detection
**Choice**: Use Python's `mimetypes` module with hardcoded fallbacks for common extensions
**Rationale**: Reliable for common audio formats (.opus, .mp3, .m4a). Fallback to `application/octet-stream` ensures playback even for unknown types.

## Implementation Tasks

### Phase 1: Backend Audio Streaming Endpoint (Critical Path)

- [ ] Implement `/api/tracks/{track_id}/stream` endpoint
  - Files: `web/backend/routers/tracks.py` (modify lines 9-14)
  - Dependencies: `from fastapi import Depends, HTTPException`, `from loguru import logger`, `import mimetypes`, `from pathlib import Path`, `from ..deps import get_db`
  - Implementation:
    1. Add database dependency: `async def stream_audio(track_id: int, db = Depends(get_db))`
    2. Query track: `cursor = db.execute("SELECT local_path, source FROM tracks WHERE id = ?", (track_id,))`
    3. Validate track exists: `row = cursor.fetchone()` → raise 404 if None
    4. Check source constraint: `if row["source"] != "local"` → raise 403 with message
    5. Get file path: `file_path = Path(row["local_path"])`
    6. Validate file exists: `if not file_path.exists()` → raise 404 with message
    7. Detect MIME type:
       - `.opus` → `audio/opus`
       - `.mp3` → `audio/mpeg`
       - `.m4a` → `audio/mp4`
       - Default → `mimetypes.guess_type()` or `application/octet-stream`
    8. Log request: `logger.info(f"Streaming track {track_id}: {file_path.name}")`
    9. Return `FileResponse(file_path, media_type=mime_type)`
  - Error Handling:
    - Track not found: `HTTPException(404, "Track not found")`
    - Non-local source: `HTTPException(403, f"Track {track_id} is not a local track (source: {row['source']}) - streaming not supported")`
    - File missing: `HTTPException(404, f"Audio file not found: {file_path}")`
    - Exceptions: Log with `logger.exception(f"Stream error for track {track_id}")`
  - Acceptance:
    - Returns audio file with correct Content-Type header for local tracks only
    - Returns 403 for non-local tracks (soundcloud, spotify, youtube)
    - Returns 404 for missing tracks/files
    - Logs all requests and errors

- [ ] Add backend logging for audio streaming
  - Files: `web/backend/routers/tracks.py` (modify)
  - Implementation:
    1. Import loguru: `from loguru import logger`
    2. Log successful streams: `logger.info(f"Streaming track {track_id}: {filename}")`
    3. Log errors: `logger.exception(f"Stream error for track {track_id}")` in except blocks
  - Acceptance: Logs visible in backend output during testing

### Phase 2: Backend Waveform Generation & Endpoint

- [ ] Rewrite `generate_waveform()` to use pydub
  - Files: `web/backend/waveform.py` (modify function at lines 27-59)
  - Dependencies: `from pydub import AudioSegment`, `import numpy as np`
  - Implementation:
    1. Replace subprocess call with pydub:
       ```python
       def generate_waveform(audio_path: str, track_id: int) -> dict:
           cache_path = get_waveform_path(track_id)

           try:
               # Load audio file with pydub
               audio = AudioSegment.from_file(audio_path)

               # Get raw audio data as numpy array
               samples = np.array(audio.get_array_of_samples())

               # Downsample to ~1000 peaks for web display
               target_peaks = 1000
               chunk_size = max(1, len(samples) // target_peaks)

               # Extract min/max for each chunk
               peaks = []
               for i in range(0, len(samples), chunk_size):
                   chunk = samples[i:i+chunk_size]
                   if len(chunk) > 0:
                       peaks.append(int(chunk.min()))
                       peaks.append(int(chunk.max()))

               # Create waveform JSON structure (WaveSurfer format)
               waveform_data = {
                   "version": 2,
                   "channels": audio.channels,
                   "sample_rate": audio.frame_rate,
                   "samples_per_pixel": chunk_size,
                   "bits": 8,
                   "length": len(samples),
                   "data": peaks
               }

               # Cache to disk
               with open(cache_path, 'w') as f:
                   json.dump(waveform_data, f)

               return waveform_data

           except Exception as e:
               raise RuntimeError(f"Failed to generate waveform: {str(e)}")
       ```
    2. Remove all subprocess/audiowaveform references
    3. Handle pydub exceptions (unsupported formats, corrupted files)
  - Acceptance:
    - Generates waveform JSON with peaks array
    - Caches to `~/.local/share/music-minion/waveforms/{track_id}.json`
    - Works with .opus, .mp3, .m4a files
    - Raises RuntimeError on failure

- [ ] Implement `/api/tracks/{track_id}/waveform` endpoint
  - Files: `web/backend/routers/tracks.py` (modify lines 17-24)
  - Dependencies: `from fastapi.responses import JSONResponse`, `from ..waveform import has_cached_waveform, generate_waveform, get_waveform_path`, `import json`
  - Implementation:
    1. Add database dependency: `async def get_waveform(track_id: int, db = Depends(get_db))`
    2. Check cache: `if has_cached_waveform(track_id):`
    3. If cached:
       - Get cache path: `cache_path = get_waveform_path(track_id)`
       - Read JSON: `with open(cache_path) as f: waveform_data = json.load(f)`
       - Log cache hit: `logger.debug(f"Waveform cache hit for track {track_id}")`
       - Return: `JSONResponse(waveform_data)`
    4. If not cached:
       - Query track: `cursor = db.execute("SELECT local_path, source FROM tracks WHERE id = ?", (track_id,))`
       - Validate track exists → raise 404 if None
       - Check source constraint: `if row["source"] != "local"` → raise 403 with message
       - Get file path: `file_path = row["local_path"]`
       - Validate file exists → raise 404 if missing
       - Log generation: `logger.info(f"Generating waveform for track {track_id}")`
       - Generate: `waveform_data = generate_waveform(file_path, track_id)`
       - Return: `JSONResponse(waveform_data)`
  - Error Handling:
    - Track not found: `HTTPException(404, "Track not found")`
    - Non-local source: `HTTPException(403, f"Track {track_id} is not a local track (source: {row['source']}) - waveform not supported")`
    - File missing: `HTTPException(404, f"Audio file not found: {file_path}")`
    - Generation failure: `HTTPException(500, f"Waveform generation failed: {str(e)}")`
    - Catch `RuntimeError` from `generate_waveform()` (pydub failures)
    - Catch `json.JSONDecodeError` for corrupted cache
    - Log all errors with track context
  - Acceptance:
    - Returns cached waveform JSON on second request for local tracks only
    - Generates waveform on first request for local tracks only
    - Returns 403 for non-local tracks (soundcloud, spotify, youtube)
    - Returns 404 for missing tracks/files
    - Returns 500 if pydub fails (unsupported format, etc.)
    - Logs cache hits and generation events

- [ ] Add waveform generation logging
  - Files: `web/backend/routers/tracks.py` (modify)
  - Implementation:
    1. Log cache hits: `logger.debug(f"Waveform cache hit for track {track_id}")`
    2. Log generation start: `logger.info(f"Generating waveform for track {track_id}")`
    3. Log errors: `logger.exception(f"Waveform error for track {track_id}")`
  - Acceptance: Logs distinguish between cache hits and new generation

### Phase 3: Frontend Graceful Degradation

- [ ] Refactor `useWavesurfer` hook for progressive enhancement
  - Files: `web/frontend/src/hooks/useWavesurfer.ts` (modify)
  - Implementation:
    1. Add error state: `const [error, setError] = useState<string | null>(null)`
    2. Separate waveform loading from audio loading:
       ```typescript
       const initWavesurfer = async () => {
         try {
           // Try to load waveform first
           let waveformData = null;
           try {
             waveformData = await getWaveformData(trackId);
           } catch (waveformError) {
             // Log but don't fail - graceful degradation
             console.warn('Waveform unavailable, using basic playback:', waveformError);
           }

           // Create WaveSurfer instance
           const wavesurfer = WaveSurfer.create({ ... });

           // Load audio with or without waveform
           const streamUrl = getStreamUrl(trackId);
           if (waveformData?.peaks) {
             wavesurfer.load(streamUrl, [waveformData.peaks]);
           } else {
             wavesurfer.load(streamUrl); // Basic playback without visualization
           }

           // Set up event listeners...
           wavesurferRef.current = wavesurfer;
         } catch (error) {
           // Audio loading failed - show error to user
           console.error('Failed to load audio:', error);
           setError('Failed to load audio. Try again.');
         }
       };
       ```
    3. Add retry function: `const retryLoad = () => { setError(null); initWavesurfer(); }`
    4. Return error and retry in hook: `return { ..., error, retryLoad }`
  - Acceptance:
    - Waveform failure (500) → audio plays without visualization
    - Audio failure → error state set
    - No console errors logged as failures (only warnings for waveform)
    - Retry function clears error and re-initializes

- [ ] Add error UI to WaveformPlayer component
  - Files: `web/frontend/src/components/WaveformPlayer.tsx` (modify)
  - Implementation:
    1. Destructure error from hook: `const { error, retryLoad, containerRef, ... } = useWavesurfer({ ... })`
    2. Add error UI before waveform container:
       ```tsx
       {error && (
         <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
           <p className="text-red-800 text-sm mb-2">{error}</p>
           <button
             onClick={retryLoad}
             className="text-red-600 underline text-sm hover:text-red-800"
           >
             Retry
           </button>
         </div>
       )}
       <div ref={containerRef} className={error ? 'hidden' : ''} />
       ```
    3. Hide waveform container when error shown
  - Acceptance:
    - Error message displays when audio fails to load
    - Retry button calls retryLoad function
    - Error auto-dismisses on successful retry
    - No error shown for waveform-only failures

### Phase 4: Testing & Validation

- [ ] Manual testing checklist
  - Files: N/A (testing procedure)
  - Test Cases:
    1. **Happy path**: Click local track → audio plays with waveform
    2. **Cache hit**: Second play of same local track uses cached waveform (verify in logs)
    3. **Play/pause**: Toggle play/pause button works for local tracks
    4. **Seek bar**: Click waveform to jump to position for local tracks
    5. **Non-local track**: Click soundcloud/spotify/youtube track → 403 error shown
    6. **Missing file**: Delete audio file → 404 error shown with retry button
    7. **Unsupported format**: Try unsupported audio format → audio plays without waveform (no error shown)
    8. **Special characters**: Play local track with spaces/unicode in filename
    9. **Multiple tracks**: Play different local tracks in sequence
    10. **Retry button**: Trigger error → click retry → audio recovers
    11. **Browser console**: No unhandled errors or warnings (except waveform degradation warning)
  - Acceptance: All 11 test cases pass

- [ ] Backend endpoint validation
  - Files: N/A (manual testing)
  - Test Commands:
    ```bash
    # Start backend
    uv run uvicorn web.backend.main:app --reload

    # Test streaming endpoint - local track
    curl -I http://localhost:8000/api/tracks/1/stream
    # Expected: 200 OK, Content-Type: audio/opus (or audio/mpeg, audio/mp4)

    # Test streaming endpoint - non-local track (if exists)
    curl -I http://localhost:8000/api/tracks/2/stream
    # Expected: 403 Forbidden if source != 'local'

    # Test waveform endpoint (first call - should generate)
    curl http://localhost:8000/api/tracks/1/waveform | jq
    # Expected: JSON with "peaks" array

    # Test waveform endpoint (second call - should use cache)
    curl http://localhost:8000/api/tracks/1/waveform | jq
    # Expected: Same JSON, logs show "cache hit"

    # Test waveform endpoint - non-local track
    curl http://localhost:8000/api/tracks/2/waveform
    # Expected: 403 Forbidden if source != 'local'

    # Test missing track
    curl -I http://localhost:8000/api/tracks/999999/stream
    # Expected: 404 Not Found

    # Check logs
    tail -f ~/.local/share/music-minion/music-minion.log
    ```
  - Acceptance: All curl commands return expected responses

- [ ] Data integrity check - tracks by source type
  - Files: N/A (manual validation)
  - Implementation:
    ```bash
    # Connect to database and check track sources
    sqlite3 ~/.local/share/music-minion/music-minion.db << 'EOF'
    SELECT source, COUNT(*) as count,
           COUNT(local_path) as with_local_path,
           COUNT(CASE WHEN local_path IS NOT NULL AND source = 'local' THEN 1 END) as local_with_path,
           COUNT(CASE WHEN local_path IS NULL AND source != 'local' THEN 1 END) as streaming_without_path
    FROM tracks
    GROUP BY source
    ORDER BY source;
    EOF
    ```
  - Expected Results:
    - `local` tracks: Should have `local_path` set, count should match `with_local_path`
    - `soundcloud` tracks: Should have `local_path` NULL, count should match `streaming_without_path`
    - `spotify` tracks: Should have `local_path` NULL, count should match `streaming_without_path`
    - `youtube` tracks: Should have `local_path` NULL, count should match `streaming_without_path`
  - Acceptance: Data integrity validated, streaming tracks have no local_path, local tracks have local_path

- [ ] Frontend integration testing
  - Files: N/A (manual testing)
  - Test Procedure:
    ```bash
    # Start frontend dev server
    cd web/frontend
    npm run dev

    # Open browser to http://localhost:5173
    # Open browser DevTools → Network tab
    # Open browser DevTools → Console tab

    # Click on track card
    # Verify:
    # - Network tab shows successful GET /api/tracks/{id}/waveform (200)
    # - Network tab shows successful GET /api/tracks/{id}/stream (200)
    # - Audio plays
    # - Waveform renders
    # - No console errors
    ```
  - Acceptance: Audio plays, waveform renders, no console errors

## Acceptance Criteria

### Functional Requirements
- ✅ Clicking local track starts audio playback within 2 seconds
- ✅ Clicking non-local track shows appropriate error (streaming not supported)
- ✅ Waveform visualization renders when available for local tracks only
- ✅ Audio plays without waveform if generation fails (graceful degradation)
- ✅ Error UI shows for audio streaming failures with retry button
- ✅ Second play of same local track uses cached waveform (sub-second load)
- ✅ Play/pause and seek controls work correctly for local tracks

### Error Handling
- ✅ Missing track (invalid ID) → 404 error
- ✅ Non-local track (soundcloud/spotify/youtube) → 403 error with source-specific message
- ✅ Missing file (track in DB, file deleted) → 404 error with helpful message
- ✅ Waveform generation failure → audio plays anyway (no user-facing error)
- ✅ Audio streaming failure → error UI with retry button
- ✅ Retry button successfully recovers from transient errors

### Logging
- ✅ Backend logs all stream requests with track ID
- ✅ Backend logs waveform cache hits vs generation
- ✅ Backend logs all errors with track context
- ✅ No silent failures (all errors logged or shown to user)

### Performance
- ✅ Cached waveform loads in <100ms
- ✅ First-time waveform generation completes in <2 seconds
- ✅ Audio streaming starts within 2 seconds

### Code Quality
- ✅ No TypeScript errors in frontend
- ✅ No Python type errors in backend (uv run ruff check passes)
- ✅ Follows functional programming patterns (no classes, pure functions)
- ✅ Error handling uses try/except with specific exceptions
- ✅ Logging uses loguru with appropriate levels (info, debug, exception)

## Files to Create/Modify

### Backend (Python)
1. **`web/backend/waveform.py`** (modify)
   - Lines 27-59: Rewrite `generate_waveform()` to use pydub instead of audiowaveform CLI
   - Add imports: `from pydub import AudioSegment`, `import numpy as np`

2. **`web/backend/routers/tracks.py`** (modify)
    - Lines 9-14: Implement `stream_audio()` endpoint with source='local' constraint
    - Lines 17-24: Implement `get_waveform()` endpoint with source='local' constraint
    - Add imports: `Depends`, `HTTPException`, `logger`, `mimetypes`, `Path`, `JSONResponse`, waveform functions
    - Update queries to include `source` column: `SELECT local_path, source FROM tracks WHERE id = ?`
    - Add source validation: `if row["source"] != "local"` → raise 403

### Frontend (TypeScript/React)
3. **`web/frontend/src/hooks/useWavesurfer.ts`** (modify)
   - Add error state
   - Refactor `initWavesurfer()` for graceful degradation
   - Add retry function
   - Return error and retryLoad in hook

4. **`web/frontend/src/components/WaveformPlayer.tsx`** (modify)
   - Destructure error and retryLoad from hook
   - Add error UI with retry button
   - Conditionally hide waveform container on error

### Supporting Files (Read-only reference)
5. **`web/backend/deps.py`** (existing, import from)
   - `get_db()` - FastAPI dependency for database connections

6. **`src/music_minion/core/database.py`** (reference only)
    - Database schema: `tracks` table with `id`, `local_path`, `source` columns
    - Source values: 'local' (has local_path), 'soundcloud', 'spotify', 'youtube' (no local_path)

## Dependencies

### External Dependencies (Already Installed)
- **Backend**: `fastapi`, `uvicorn`, `loguru`, `sqlite3` (stdlib), `pydub`, `numpy`
- **Frontend**: `wavesurfer.js`, `@react-spring/web`, `@use-gesture/react`

### Internal Dependencies
- Backend `tracks.py` depends on:
  - `web/backend/deps.py` (get_db)
  - `web/backend/waveform.py` (waveform functions)
  - `src/music_minion/core/database.py` (database connection)
- Frontend `useWavesurfer.ts` depends on:
  - `web/frontend/src/api/tracks.ts` (getStreamUrl, getWaveformData)
- Frontend `WaveformPlayer.tsx` depends on:
  - `web/frontend/src/hooks/useWavesurfer.ts`

### Task Dependencies
- **Phase 1 blocks Phase 4**: Audio streaming must work before testing playback
- **Phase 2 independent of Phase 1**: Can implement in parallel
- **Phase 3 depends on Phases 1 & 2**: Frontend error handling needs backend endpoints implemented
- **Phase 4 depends on all**: Testing requires complete implementation

## Edge Cases

### Handled by Implementation
1. **Unicode file paths**: `Path` objects handle encoding correctly
2. **Symbolic links**: `Path.exists()` follows symlinks correctly
3. **Large files (>100MB)**: Browser handles streaming automatically
4. **Concurrent waveform generation**: Last write wins (acceptable for single user)
5. **Corrupted waveform cache**: Catch `json.JSONDecodeError`, re-raise 500 error
6. **Missing MIME type**: Fallback to `application/octet-stream`

### Out of Scope
1. **Disk space management**: Cache grows unbounded (acceptable for personal project)
2. **HTTP range requests**: Not needed for basic streaming
3. **Access control**: Single-user project, no authentication needed
4. **Waveform cache warming**: Pre-generation during library scan (future enhancement)

## Implementation Notes

### Progressive Enhancement Flow
```
User clicks track
  ↓
ComparisonView.playTrack(trackId)
  ↓
useWavesurfer hook initializes
  ↓
Try: getWaveformData(trackId)
  ├─ Success: waveformData = {...}
  └─ Failure: waveformData = null (log warning, continue)
  ↓
Try: wavesurfer.load(streamUrl, waveformData ? [peaks] : undefined)
  ├─ Success: audio plays (with or without waveform)
  └─ Failure: setError('Failed to load audio')
  ↓
Render WaveformPlayer
  ├─ Error exists: Show error UI with retry button
  └─ No error: Show waveform container (may be empty if waveform failed)
```

### Error Handling Strategy
- **Backend 404**: Track or file not found → propagate to frontend → show error
- **Backend 500**: Server error (audiowaveform missing, generation failed) → different handling:
  - Waveform endpoint 500 → frontend catches, degrades gracefully (no error shown)
  - Stream endpoint 500 → frontend catches, shows error with retry
- **Frontend network error**: Fetch failed → show "Unable to load audio" error
- **Frontend retry**: Clears error state, re-initializes WaveSurfer from scratch

### Logging Strategy
- **Info level**: Stream requests, waveform generation start
- **Debug level**: Cache hits (verbose during normal operation)
- **Exception level**: All errors with stack traces (includes track context)
- **Frontend console.warn**: Waveform degradation (not an error condition)
- **Frontend console.error**: Audio loading failures (requires user action)

---

## Testing After Implementation

Run these commands to validate the implementation:

```bash
# Backend tests
uv run uvicorn web.backend.main:app --reload &
sleep 2
curl -I http://localhost:8000/api/tracks/1/stream  # Expect 200 OK (local track)
curl http://localhost:8000/api/tracks/1/waveform | jq  # Expect JSON (local track)
curl http://localhost:8000/api/tracks/1/waveform | jq  # Expect cache hit in logs
curl -I http://localhost:8000/api/tracks/2/stream  # Expect 403 Forbidden (non-local track)
curl http://localhost:8000/api/tracks/2/waveform  # Expect 403 Forbidden (non-local track)

# Frontend tests
cd web/frontend && npm run dev &
# Open http://localhost:5173 and click local track
# Verify audio plays and waveform renders
# Click non-local track
# Verify appropriate error message displays

# Cleanup
killall uvicorn node
```

Expected outcome: Audio plays with waveform visualization for local tracks only, appropriate errors for non-local tracks, no console errors, backend logs show requests.
