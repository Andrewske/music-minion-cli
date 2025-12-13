# Web UI Audio Playback Fixes Implementation Plan

## Overview

Fix 15 critical issues identified in code review of web UI audio playback feature. Addresses security vulnerabilities (path traversal), memory leaks, code duplication, performance bottlenecks, and type safety issues. Follows strict functional programming principles with pure functions, immutable data, and explicit state passing.

**Estimated Effort**: 4-6 hours
**Test Coverage Target**: ≥70% for new code
**Breaking Changes**: Acceptable (personal project, single user)

## Architecture Decisions

- **Security First**: Add path validation layer before any file serving to prevent directory traversal attacks
- **Type Safety**: Align Pydantic schemas (backend) with TypeScript interfaces (frontend) for WaveformData
- **Pure Functions**: Extract helpers as pure functions with explicit dependencies (no global state)
- **Performance**: Vectorize waveform generation using numpy operations (10-100x speedup)
- **Memory Management**: Fix WaveSurfer instance lifecycle to prevent memory leaks on retry
- **DRY Principle**: Eliminate 150+ lines of duplicated code in useWavesurfer hook
- **Progressive Enhancement**: Maintain graceful degradation when waveform fails but audio works

## Implementation Tasks

### Phase 1: Security Infrastructure (CRITICAL)

- [ ] Create path security validation module
  - Files: `src/music_minion/core/path_security.py` (new)
  - Implementation:
    ```python
    def is_path_within_library(file_path: Path, library_paths: list[str]) -> bool:
        """Pure function - validates path is within allowed directories."""
        # Use Path.resolve() to handle symlinks and relative paths
        # Check if resolved path is child of any library root

    def validate_track_path(file_path: Path, config: MusicConfig) -> Optional[Path]:
        """Pure function - returns validated path or None."""
        # Combine existence check + library boundary validation
    ```
  - Tests: `web/backend/tests/test_path_security.py` (new)
  - Acceptance:
    - Path traversal attacks (`../../../etc/passwd`) blocked
    - Symlinks pointing outside library rejected
    - Valid paths within library allowed
    - All tests pass with ≥80% coverage

- [ ] Add config dependency injection for FastAPI
  - Files: `web/backend/deps.py` (modify)
  - Implementation:
    ```python
    def get_config() -> Config:
        """FastAPI dependency for configuration."""
        return load_config()
    ```
  - Tests: Manual verification in Phase 3
  - Acceptance: Config accessible via `Depends(get_config)` in routes

### Phase 2: Type Safety & Schema Alignment (CRITICAL)

- [ ] Create complete Pydantic schema for WaveformData
  - Files: `web/backend/schemas.py` (modify)
  - Implementation:
    ```python
    class WaveformData(BaseModel):
        version: int = 2
        channels: int
        sample_rate: int
        samples_per_pixel: int
        bits: int = 8
        length: int
        peaks: list[int]

        model_config = {"frozen": True}  # Immutable
    ```
  - Tests: `web/backend/tests/test_schemas.py` (verify serialization)
  - Acceptance:
    - Schema matches actual waveform.py output
    - Immutable (frozen) configuration enforced
    - All fields have correct types

- [ ] Update TypeScript WaveformData interface to match backend
  - Files: `web/frontend/src/types/index.ts` (modify)
  - Implementation:
    ```typescript
    export interface WaveformData {
      version: number;
      channels: number;          // ADD
      sample_rate: number;
      samples_per_pixel: number; // ADD
      bits: number;              // ADD
      length: number;            // ADD
      peaks: number[];
    }
    ```
  - Tests: TypeScript compilation (strict mode)
  - Acceptance:
    - Interface matches Pydantic schema exactly
    - No TypeScript errors in consuming code
    - Optional fields properly marked with `?`

### Phase 3: Backend Security & Code Quality (CRITICAL)

- [ ] Extract pure helper functions in tracks router
  - Files: `web/backend/routers/tracks.py` (modify)
  - Implementation:
    ```python
    # Add at top of file
    AUDIO_MIME_TYPES: dict[str, str] = {
        ".opus": "audio/opus",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
    }

    def get_track_path(track_id: int, db_conn: Connection) -> Optional[Path]:
        """Pure function - query track path from database."""
        cursor = db_conn.execute(
            "SELECT local_path FROM tracks WHERE id = ?", (track_id,)
        )
        row = cursor.fetchone()
        return Path(row["local_path"]) if row else None

    def get_mime_type(file_path: Path) -> str:
        """Pure function - deterministic MIME type detection."""
        mime = AUDIO_MIME_TYPES.get(file_path.suffix.lower())
        if mime:
            return mime
        guessed, _ = mimetypes.guess_type(str(file_path))
        return guessed or "application/octet-stream"
    ```
  - Tests: `web/backend/tests/test_tracks.py` (unit tests for helpers)
  - Acceptance:
    - Helper functions are pure (no side effects)
    - MIME type detection works for all supported formats
    - Database query duplication eliminated

- [ ] Refactor stream_audio endpoint with security validation
  - Files: `web/backend/routers/tracks.py` (modify)
  - Implementation:
    ```python
    @router.get("/tracks/{track_id}/stream")
    async def stream_audio(
        track_id: int,
        db=Depends(get_db),
        config: Config = Depends(get_config)
    ):
        file_path = get_track_path(track_id, db)
        if not file_path:
            raise HTTPException(404, "Track not found")

        # SECURITY: Validate path within library
        from music_minion.core.path_security import validate_track_path
        validated = validate_track_path(file_path, config.music)
        if not validated:
            logger.warning(f"Blocked access outside library: {file_path}")
            raise HTTPException(403, "Access denied")

        logger.info(f"Streaming track {track_id}: {validated.name}")
        return FileResponse(validated, media_type=get_mime_type(validated))
    ```
  - Tests: Integration tests with valid/invalid paths
  - Acceptance:
    - Path traversal attempts return 403
    - Valid tracks stream successfully
    - Proper MIME types returned
    - No redundant try/except blocks

- [ ] Refactor get_waveform endpoint with security validation
  - Files: `web/backend/routers/tracks.py` (modify)
  - Implementation: Apply same helper functions and path validation as stream_audio
  - Tests: Integration tests for waveform generation
  - Acceptance:
    - Path validation applied consistently
    - Cache logic simplified (no exception-based control flow)
    - Corrupted cache files regenerated automatically

### Phase 4: Backend Performance & Error Handling (IMPORTANT)

- [ ] Add waveform size limits and custom exceptions
  - Files: `web/backend/waveform.py` (modify)
  - Implementation:
    ```python
    MAX_AUDIO_SIZE_MB = 100  # Prevent OOM

    class AudioTooLargeError(Exception):
        """File exceeds size limit for waveform generation."""

    class FFmpegNotFoundError(Exception):
        """ffmpeg not installed or not in PATH."""
    ```
  - Tests: `web/backend/tests/test_waveform.py`
  - Acceptance:
    - Files >100MB rejected with clear error
    - Custom exceptions raised appropriately

- [ ] Vectorize waveform peak extraction
  - Files: `web/backend/waveform.py` (modify - replace lines 43-47)
  - Implementation:
    ```python
    # Vectorized min/max computation (10-100x faster than Python loop)
    num_chunks = len(samples) // chunk_size
    truncated = samples[:num_chunks * chunk_size]
    chunks = truncated.reshape(num_chunks, chunk_size)

    min_vals = chunks.min(axis=1)
    max_vals = chunks.max(axis=1)

    # Interleave min/max for WaveSurfer format
    peaks = np.empty(num_chunks * 2, dtype=int)
    peaks[0::2] = min_vals
    peaks[1::2] = max_vals
    peaks = peaks.tolist()
    ```
  - Tests: Verify output matches original algorithm (correctness)
  - Acceptance:
    - Peak values identical to original loop-based approach
    - Performance improvement ≥10x on large files
    - No numpy overflow/underflow issues

- [ ] Improve error messages with ffmpeg detection
  - Files: `web/backend/waveform.py` (modify)
  - Implementation:
    ```python
    # Add size check before loading
    file_size_mb = Path(audio_path).stat().st_size / (1024 * 1024)
    if file_size_mb > MAX_AUDIO_SIZE_MB:
        raise AudioTooLargeError(
            f"File too large: {file_size_mb:.1f}MB > {MAX_AUDIO_SIZE_MB}MB"
        )

    try:
        audio = AudioSegment.from_file(audio_path)
    except FileNotFoundError as e:
        if "ffmpeg" in str(e).lower():
            raise FFmpegNotFoundError(
                "ffmpeg not found. Install: apt install ffmpeg"
            ) from e
        raise
    except Exception as e:
        if "opus" in str(e).lower():
            raise RuntimeError(
                "Opus codec not supported. Ensure ffmpeg built with libopus."
            ) from e
        raise RuntimeError(f"Failed to decode audio: {type(e).__name__}") from e
    ```
  - Tests: Mock missing ffmpeg, test error messages
  - Acceptance:
    - Missing ffmpeg produces helpful error
    - Opus codec issues detected and reported
    - Users can diagnose setup problems from errors

### Phase 5: Frontend Memory Leak & Code Duplication (CRITICAL)

- [ ] Extract pure helper functions in useWavesurfer hook
  - Files: `web/frontend/src/hooks/useWavesurfer.ts` (modify - add at top)
  - Implementation:
    ```typescript
    function createWavesurferConfig(container: HTMLDivElement) {
      return {
        container,
        waveColor: '#3b82f6',
        progressColor: '#1d4ed8',
        height: 80,
        normalize: true,
        backend: 'MediaElement',
      };
    }

    function formatError(error: unknown): string {
      const msg = error instanceof Error ? error.message : String(error);

      if (msg.includes('waveform')) {
        return 'Failed to load waveform. Playing audio only.';
      }
      if (msg.includes('network') || msg.includes('fetch')) {
        return 'Network error. Check connection and retry.';
      }
      if (msg.includes('decode')) {
        return 'Audio format not supported by browser.';
      }
      return `Failed to load audio: ${msg}`;
    }
    ```
  - Tests: Manual verification (better error messages)
  - Acceptance:
    - Pure functions with no side effects
    - Error messages differentiate failure types

- [ ] Fix memory leak in retryLoad function
  - Files: `web/frontend/src/hooks/useWavesurfer.ts` (modify)
  - Implementation:
    ```typescript
    const retryLoad = useCallback(() => {
      // FIX: Destroy old instance BEFORE creating new one
      if (wavesurferRef.current) {
        wavesurferRef.current.destroy();
        wavesurferRef.current = null;
      }
      setError(null);
      // Re-trigger initialization
    }, []);
    ```
  - Tests: Chrome DevTools Memory tab (manual test)
  - Acceptance:
    - Click "Retry" 10 times, no instance accumulation
    - Heap snapshot shows single WaveSurfer instance max
    - No memory growth on repeated retries

- [ ] Consolidate initialization logic (remove duplication)
  - Files: `web/frontend/src/hooks/useWavesurfer.ts` (modify - delete lines 107-166)
  - Implementation:
    - Extract `initWavesurfer` as `useCallback` (memoized)
    - Call from both `useEffect` and `retryLoad`
    - Remove 150+ lines of duplicate code
  - Tests: Functional verification (audio still plays)
  - Acceptance:
    - File reduced from ~180 to ~140 lines
    - Zero code duplication
    - Audio playback and retry both work

- [ ] Fix useEffect dependency array
  - Files: `web/frontend/src/hooks/useWavesurfer.ts` (modify)
  - Implementation:
    ```typescript
    const handleReady = useCallback((duration: number) => {
      setDuration(duration);
      onReady?.(duration);
    }, [onReady]);

    const handleSeek = useCallback((progress: number) => {
      onSeek?.(progress);
    }, [onSeek]);

    useEffect(() => {
      // ... initialization ...
    }, [trackId, handleReady, handleSeek]);  // FIX: Complete dependencies
    ```
  - Tests: ESLint exhaustive-deps rule passes
  - Acceptance:
    - No ESLint warnings
    - No stale closure bugs
    - Callbacks properly memoized

### Phase 6: Frontend UX Improvements (NICE TO HAVE)

- [ ] Add accessibility labels to controls
  - Files: `web/frontend/src/components/WaveformPlayer.tsx` (modify)
  - Implementation:
    ```tsx
    <button
      onClick={togglePlayPause}
      aria-label={isPlaying ? 'Pause' : 'Play'}
      className="... focus:ring-2 focus:ring-blue-500"
      disabled={!!error}
    >
      <span aria-hidden="true">{isPlaying ? '⏸️' : '▶️'}</span>
    </button>

    {error && (
      <div role="alert" aria-live="polite" className="...">
        <p className="text-red-800 text-sm mb-2">{error}</p>
        <button onClick={retryLoad} className="...">
          Retry
        </button>
      </div>
    )}
    ```
  - Tests: Manual keyboard navigation and screen reader testing
  - Acceptance:
    - Tab navigation works
    - Space/Enter activates buttons
    - ARIA labels present
    - Focus ring visible

- [ ] Add waveform placeholder when error occurs
  - Files: `web/frontend/src/components/WaveformPlayer.tsx` (modify)
  - Implementation:
    ```tsx
    <div className="mb-4">
      {error ? (
        <div className="h-20 bg-gray-100 rounded flex items-center justify-center">
          <div className="text-gray-400 text-sm">
            Waveform unavailable
          </div>
        </div>
      ) : (
        <div ref={containerRef} />
      )}
    </div>
    ```
  - Tests: Visual verification
  - Acceptance:
    - Placeholder shows on error
    - UI doesn't jump when waveform fails
    - Maintains consistent layout

### Phase 7: Configuration & Documentation (IMPORTANT)

- [ ] Document ffmpeg runtime dependency
  - Files: `pyproject.toml` (modify)
  - Implementation:
    ```toml
    dependencies = [
        # ...
        "pydub>=0.25.1", # Audio waveform (requires ffmpeg runtime)
    ]

    # NOTE: System dependencies (install separately):
    # - ffmpeg: apt install ffmpeg (Debian/Ubuntu)
    #           brew install ffmpeg (macOS)
    ```
  - Tests: N/A (documentation only)
  - Acceptance:
    - Users know ffmpeg is required
    - Installation instructions provided

- [ ] Add environment-based CORS configuration
  - Files: `web/backend/main.py` (modify)
  - Implementation:
    ```python
    import os

    # CORS: Allow environment override for production
    allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
    allowed_origins = (
        allowed_origins_env.split(",") if allowed_origins_env
        else ["http://localhost:5173"]  # Dev default
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    ```
  - Tests: Manual verification with env var
  - Acceptance:
    - Dev mode works with default
    - Production can override via ALLOWED_ORIGINS
    - Multiple origins supported (comma-separated)

## Testing Requirements

### Backend Unit Tests (NEW FILES)

- [ ] Create `web/backend/tests/test_path_security.py`
  - Tests:
    - `test_directory_traversal_blocked()` - Verify `../` attacks fail
    - `test_symlink_escape_blocked()` - Verify symlinks outside library fail
    - `test_valid_path_allowed()` - Verify legitimate paths pass
    - `test_nonexistent_file_rejected()` - Verify existence check works
  - Coverage target: ≥80%

- [ ] Create `web/backend/tests/test_waveform.py`
  - Tests:
    - `test_waveform_size_limit()` - Files >100MB raise AudioTooLargeError
    - `test_ffmpeg_not_found_error()` - Missing ffmpeg raises FFmpegNotFoundError
    - `test_vectorized_peaks_correctness()` - Output matches original algorithm
    - `test_opus_codec_error()` - Opus decode failure has helpful message
  - Coverage target: ≥75%

- [ ] Create `web/backend/tests/test_tracks.py`
  - Tests:
    - `test_get_track_path_valid()` - Returns Path for valid track ID
    - `test_get_track_path_invalid()` - Returns None for invalid track ID
    - `test_get_mime_type_opus()` - Returns "audio/opus" for .opus files
    - `test_get_mime_type_fallback()` - Uses mimetypes for unknown extensions
  - Coverage target: ≥80%

### Frontend Manual Tests

- [ ] Memory leak verification
  - Procedure:
    1. Open Chrome DevTools → Memory tab
    2. Take baseline heap snapshot
    3. Click "Retry" button 10 times
    4. Take second heap snapshot
    5. Compare snapshots
  - Acceptance: No WaveSurfer instance accumulation

- [ ] Accessibility verification
  - Procedure:
    1. Tab through all controls
    2. Activate buttons with Space/Enter
    3. (Optional) Test with screen reader
  - Acceptance:
    - All controls keyboard accessible
    - Focus indicators visible
    - ARIA labels announced

## Acceptance Criteria

- [ ] All backend unit tests pass with ≥70% coverage
- [ ] No TypeScript compilation errors (strict mode)
- [ ] No ESLint warnings (exhaustive-deps rule)
- [ ] Security: Path traversal attacks blocked (403 responses)
- [ ] Performance: Waveform generation ≥10x faster on large files
- [ ] Memory: No WaveSurfer instance leaks on retry
- [ ] Code quality: No code duplication in useWavesurfer hook
- [ ] UX: Audio playback works even when waveform fails
- [ ] Documentation: ffmpeg requirement clearly stated

## Files to Create/Modify

### New Files
1. `src/music_minion/core/path_security.py` - Path validation utilities
2. `web/backend/tests/test_path_security.py` - Security tests
3. `web/backend/tests/test_waveform.py` - Waveform tests
4. `web/backend/tests/test_tracks.py` - Tracks router tests

### Modified Files
5. `web/backend/deps.py` - Add config dependency injection
6. `web/backend/schemas.py` - Complete WaveformData schema
7. `web/backend/routers/tracks.py` - Security, helpers, refactored endpoints
8. `web/backend/waveform.py` - Vectorization, size limits, better errors
9. `web/backend/main.py` - Environment-based CORS
10. `web/frontend/src/types/index.ts` - Align WaveformData with backend
11. `web/frontend/src/hooks/useWavesurfer.ts` - Fix leak, remove duplication
12. `web/frontend/src/components/WaveformPlayer.tsx` - Accessibility, placeholder
13. `pyproject.toml` - Document ffmpeg dependency

## Dependencies

### External Dependencies
- **ffmpeg** (runtime): Required by pydub for audio processing
  - Debian/Ubuntu: `apt install ffmpeg`
  - macOS: `brew install ffmpeg`
  - Must support Opus codec (usually default)

### Internal Dependencies
- Phase 1 must complete before Phase 3 (security validation needed)
- Phase 2 should complete before Phase 4 (types needed for waveform)
- Phases 4 and 5 can run in parallel (independent)
- Phase 6 depends on Phase 5 (hook refactor first)
- Phase 7 is independent (can run anytime)

### Package Dependencies (already in pyproject.toml)
- `pydub>=0.25.1` - Audio processing
- `numpy` - Vectorized operations (transitive via other deps)
- `fastapi>=0.109.0` - Web framework
- `pytest` - Testing framework

## Implementation Order

1. **Phase 1** - Security infrastructure (foundation)
2. **Phase 2** - Type safety (foundation)
3. **Phase 3** - Backend refactor (uses 1 & 2)
4. **Phase 4** + **Phase 5** - Performance & memory fixes (parallel)
5. **Phase 6** - UX polish (after Phase 5)
6. **Phase 7** - Config & docs (anytime)

## Notes for OpenCode Orchestrator

- This is a **personal project** (single user) - no backwards compatibility needed
- **Strict FP principles**: Pure functions, immutable data, explicit state passing
- **No classes** except dataclass/NamedTuple or framework requirements
- Functions should be ≤20 lines, ≤3 nesting levels
- Type hints required for all Python parameters and returns
- No `any` in TypeScript
- Absolute imports preferred
- Use existing patterns from codebase (see `domain/playlists/importers.py` for path resolution example)
