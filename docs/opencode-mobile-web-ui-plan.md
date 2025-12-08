# Mobile Web UI for ELO Track Comparisons - OpenCode Implementation Plan

## Overview

Build a mobile-first web interface for Music Minion's ELO track comparison system. Users can rate tracks from their phone browser with waveform visualization, swipe gestures for voting, and audio streaming from the server.

**Key Features:**
- Two-track comparison cards (stacked vertically)
- Swipe right = mark as winner, swipe left = archive
- Tap card = play that track
- Waveform visualization with seeking (like Poweramp)
- Number keys 1-9 for quick seek (10%-90%)
- Session-based comparisons with progress tracking

## Architecture Decisions

### Decision 1: Monorepo Integration
**Choice:** Add `web/` folder to existing music-minion-cli repo
**Rationale:**
- Shared SQLite database (no sync complexity)
- Reuse existing domain logic (`domain/rating/elo.py`, `domain/rating/database.py`)
- Single deployment and versioning

### Decision 2: FastAPI Backend
**Choice:** FastAPI for REST API
**Rationale:**
- Modern Python framework with async support
- Pydantic for type-safe schemas
- Easy integration with existing SQLite database
- Built-in OpenAPI docs

### Decision 3: Pre-computed Waveforms
**Choice:** Generate waveforms server-side with `audiowaveform` CLI, cache as JSON
**Rationale:**
- Client-side generation is slow and CPU-intensive
- Pre-computing provides instant display
- Small storage cost (~10KB per track)
- BBC's audiowaveform is industry-standard

### Decision 4: React + Vite Frontend
**Choice:** React with Vite build tool
**Rationale:**
- User has React experience
- Vite provides fast HMR and builds
- wavesurfer.js has excellent React support
- Rich gesture library ecosystem

### Decision 5: Zustand + React Query
**Choice:** Zustand for UI state, React Query for server state
**Rationale:**
- React Query handles caching, revalidation, optimistic updates
- Zustand is minimal boilerplate for simple UI state
- Clear separation of concerns

### Decision 6: @use-gesture/react for Swipes
**Choice:** @use-gesture over Framer Motion
**Rationale:**
- Smaller bundle size (9KB vs 35KB)
- More control over gesture physics
- Works seamlessly with react-spring for animations

## Implementation Tasks

### Phase 1: Backend Foundation

#### 1.1 Project Structure Setup
- [ ] Create backend directory structure
  - Files:
    - `web/backend/__init__.py` (new)
    - `web/backend/main.py` (new)
    - `web/backend/routers/__init__.py` (new)
    - `web/backend/routers/comparisons.py` (new)
    - `web/backend/routers/tracks.py` (new)
    - `web/backend/schemas.py` (new)
    - `web/backend/waveform.py` (new)
    - `web/backend/deps.py` (new)
  - Tests: None (directory structure)
  - Acceptance: All directories and `__init__.py` files created

- [ ] Update pyproject.toml with web dependencies
  - Files: `pyproject.toml` (modify)
  - Changes: Add `[project.optional-dependencies]` section with:
    ```toml
    web = [
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "python-multipart>=0.0.6",
    ]
    ```
  - Tests: Run `uv sync --extra web` successfully
  - Acceptance: Dependencies install without errors

#### 1.2 Pydantic Schemas
- [ ] Define request/response models in schemas.py
  - Files: `web/backend/schemas.py` (new)
  - Implement:
    - `TrackInfo` (id, title, artist, album, year, bpm, genre, rating, comparison_count, duration, has_waveform)
    - `ComparisonPair` (track_a, track_b, session_id)
    - `StartSessionRequest` (target_comparisons, source_filter, genre_filter, year_filter, playlist_id)
    - `StartSessionResponse` (session_id, total_tracks, pair)
    - `RecordComparisonRequest` (session_id, track_a_id, track_b_id, winner_id)
    - `RecordComparisonResponse` (success, comparisons_done, target_comparisons, session_complete, next_pair)
    - `WaveformData` (peaks, duration, sample_rate)
  - Tests: `web/backend/tests/test_schemas.py`
    - Validate all models with sample data
    - Test required vs optional fields
    - Test type coercion
  - Acceptance: All schemas serialize/deserialize correctly

#### 1.3 FastAPI Application Setup
- [ ] Create main FastAPI app with CORS and routers
  - Files: `web/backend/main.py` (new)
  - Implement:
    - FastAPI app initialization
    - CORS middleware (allow localhost:5173 for dev)
    - Include routers for comparisons and tracks
    - Health check endpoint: `GET /health`
  - Tests: `web/backend/tests/test_main.py`
    - Test health check returns 200
    - Test CORS headers present
  - Acceptance: Server starts on port 8000, health check responds

#### 1.4 Database Dependencies
- [ ] Create FastAPI dependency for database connections
  - Files: `web/backend/deps.py` (new)
  - Implement:
    - `get_db()` dependency using `get_db_connection()` from `music_minion.core.database`
    - Session management (context manager)
  - Tests: `web/backend/tests/test_deps.py`
    - Test connection opens and closes properly
    - Test connection is reusable across requests
  - Acceptance: Dependencies inject database connections correctly

#### 1.5 Comparison Session Endpoints
- [ ] Implement comparison session management
  - Files: `web/backend/routers/comparisons.py` (new)
  - Endpoints:
    - `POST /api/comparisons/session` - Start new session
      - Reuse `get_filtered_tracks()` from `music_minion.domain.rating.database`
      - Generate session_id (UUID)
      - Use `select_strategic_pair()` from `music_minion.domain.rating.elo`
    - `GET /api/comparisons/next-pair?session_id={id}` - Get next pair
      - Use `select_strategic_pair()` with filtered tracks
    - `POST /api/comparisons/record` - Record comparison result
      - Reuse `get_or_create_rating()`, `update_ratings()`, `get_k_factor()`, `record_comparison()`
      - Return next pair automatically
  - Tests: `web/backend/tests/test_comparisons.py`
    - Test session creation with various filters
    - Test next-pair selection follows strategic pairing
    - Test record comparison updates database
    - Test session completion detection
  - Acceptance:
    - Sessions start with valid track pairs
    - Comparisons record atomically
    - Ratings update correctly

#### 1.6 Audio Streaming Endpoint
- [ ] Implement audio file streaming with range support
  - Files: `web/backend/routers/tracks.py` (new)
  - Endpoints:
    - `GET /api/tracks/{track_id}/stream` - Stream audio file
      - Query track from database
      - Return FileResponse with `Accept-Ranges: bytes` header
      - Auto-detect media type (.mp3 → audio/mpeg, .m4a → audio/mp4, .opus → audio/opus)
  - Tests: `web/backend/tests/test_tracks.py`
    - Test streaming returns correct media type
    - Test range requests work (for seeking)
    - Test 404 for non-existent tracks
  - Acceptance:
    - Audio streams correctly
    - Seeking works in browser
    - All supported formats (MP3, M4A, Opus) work

#### 1.7 Waveform Generation & Caching
- [ ] Implement waveform generation with audiowaveform CLI
  - Files: `web/backend/waveform.py` (new)
  - Implement:
    - `get_waveform_path(track_id)` - Returns cache path
    - `has_cached_waveform(track_id)` - Check cache existence
    - `generate_waveform(audio_path, track_id)` - Call audiowaveform CLI
      - Command: `audiowaveform -i {audio_path} -o {output_path} --pixels-per-second 50 -b 8`
    - Cache directory: `~/.local/share/music-minion/waveforms/`
  - Tests: `web/backend/tests/test_waveform.py`
    - Test cache directory creation
    - Test waveform generation produces valid JSON
    - Test caching works (second call uses cache)
    - Test error handling for corrupted audio files
  - Acceptance:
    - Waveforms generate successfully
    - Cache reduces generation time to near-zero
    - JSON format compatible with wavesurfer.js

- [ ] Add waveform endpoint to tracks router
  - Files: `web/backend/routers/tracks.py` (modify)
  - Endpoints:
    - `GET /api/tracks/{track_id}/waveform` - Get waveform peaks
      - Check cache, generate if missing
      - Return JSON with peaks array
  - Tests: `web/backend/tests/test_tracks.py` (add)
    - Test returns cached waveform
    - Test generates on first request
    - Test 404 for non-existent tracks
  - Acceptance: Waveforms available via API

#### 1.8 Archive Track Endpoint
- [ ] Implement track archiving
  - Files: `web/backend/routers/tracks.py` (modify)
  - Endpoints:
    - `POST /api/tracks/{track_id}/archive` - Archive track
      - Update `rating='archive'` in tracks table
  - Tests: `web/backend/tests/test_tracks.py` (add)
    - Test archiving updates database
    - Test archived tracks excluded from comparisons
  - Acceptance: Archived tracks no longer appear in pairs

### Phase 2: Frontend Setup

#### 2.1 Vite + React Project Initialization
- [ ] Create Vite React TypeScript project
  - Files:
    - `web/frontend/package.json` (new)
    - `web/frontend/vite.config.ts` (new)
    - `web/frontend/tsconfig.json` (new)
    - `web/frontend/index.html` (new)
    - `web/frontend/src/main.tsx` (new)
    - `web/frontend/src/App.tsx` (new)
  - Commands:
    ```bash
    cd web
    npm create vite@latest frontend -- --template react-ts
    ```
  - Tests: None (project scaffold)
  - Acceptance: `npm run dev` starts dev server on port 5173

- [ ] Install dependencies
  - Files: `web/frontend/package.json` (modify)
  - Dependencies:
    ```json
    {
      "dependencies": {
        "react": "^18.3.0",
        "react-dom": "^18.3.0",
        "wavesurfer.js": "^7.8.0",
        "@use-gesture/react": "^10.3.0",
        "@react-spring/web": "^9.7.0",
        "@tanstack/react-query": "^5.51.0",
        "zustand": "^4.5.0"
      }
    }
    ```
  - Tests: None (dependency installation)
  - Acceptance: `npm install` completes successfully

#### 2.2 Tailwind CSS Setup
- [ ] Configure Tailwind CSS
  - Files:
    - `web/frontend/tailwind.config.js` (new)
    - `web/frontend/postcss.config.js` (new)
    - `web/frontend/src/styles/index.css` (new)
  - Install: `tailwindcss`, `postcss`, `autoprefixer`
  - Configure content paths, mobile-first breakpoints
  - Tests: None (configuration)
  - Acceptance: Tailwind classes work in components

#### 2.3 Vite Proxy Configuration
- [ ] Add API proxy to Vite config
  - Files: `web/frontend/vite.config.ts` (modify)
  - Configuration:
    ```typescript
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true
        }
      }
    }
    ```
  - Tests: Manual test (fetch from `/api/health`)
  - Acceptance: API requests proxy to backend

#### 2.4 TypeScript Types
- [ ] Define TypeScript types matching backend schemas
  - Files: `web/frontend/src/types/index.ts` (new)
  - Types:
    - `Track` (matching `TrackInfo` schema)
    - `ComparisonPair`
    - `StartSessionRequest`
    - `StartSessionResponse`
    - `RecordComparisonRequest`
    - `RecordComparisonResponse`
    - `WaveformData`
  - Tests: None (type definitions)
  - Acceptance: Types match backend Pydantic models exactly

#### 2.5 API Client
- [ ] Create API client with fetch wrapper
  - Files:
    - `web/frontend/src/api/client.ts` (new)
    - `web/frontend/src/api/comparisons.ts` (new)
    - `web/frontend/src/api/tracks.ts` (new)
  - Implement:
    - `client.ts`: Base fetch wrapper with error handling, JSON parsing
    - `comparisons.ts`: `startSession()`, `getNextPair()`, `recordComparison()`
    - `tracks.ts`: `getStreamUrl()`, `getWaveformData()`, `archiveTrack()`
  - Tests: `web/frontend/src/api/__tests__/client.test.ts`
    - Test error handling
    - Test JSON parsing
    - Mock fetch responses
  - Acceptance: All API calls typed and functional

### Phase 3: Core UI Components

#### 3.1 Zustand Store
- [ ] Create comparison state store
  - Files: `web/frontend/src/stores/comparisonStore.ts` (new)
  - State:
    - `sessionId: string | null`
    - `currentPair: ComparisonPair | null`
    - `playingTrackId: number | null`
    - `comparisonsCompleted: number`
    - `targetComparisons: number`
  - Actions:
    - `setSession(sessionId, pair)`
    - `setPlaying(trackId)`
    - `incrementCompleted()`
  - Tests: `web/frontend/src/stores/__tests__/comparisonStore.test.ts`
    - Test state updates
    - Test derived values
  - Acceptance: Store manages session state correctly

#### 3.2 React Query Hooks
- [ ] Create comparison session hooks
  - Files: `web/frontend/src/hooks/useComparison.ts` (new)
  - Hooks:
    - `useComparisonSession(options)` - Start/fetch session
    - `useRecordComparison()` - Mutation for recording
  - Uses React Query for caching and optimistic updates
  - Tests: `web/frontend/src/hooks/__tests__/useComparison.test.ts`
    - Test query invalidation after mutation
    - Test optimistic updates
  - Acceptance: Hooks manage server state correctly

#### 3.3 TrackCard Component
- [ ] Create track card display component
  - Files: `web/frontend/src/components/TrackCard.tsx` (new)
  - Props: `track: Track`, `isPlaying: boolean`, `onTap: () => void`
  - Display:
    - Artist - Title (large, bold)
    - Album • Year • BPM (smaller, gray)
    - Rating with icon (⭐ if ≥10 comparisons, ⚠️ if <10)
    - Playing indicator (▶ icon when active)
  - Styling: Mobile-first, min touch target 44x44px
  - Tests: `web/frontend/src/components/__tests__/TrackCard.test.tsx`
    - Test renders all track info
    - Test displays correct icon for rating
    - Test onTap callback fires
  - Acceptance: Card displays track info correctly

#### 3.4 SessionProgress Component
- [ ] Create session progress indicator
  - Files: `web/frontend/src/components/SessionProgress.tsx` (new)
  - Props: `completed: number`, `target: number`
  - Display: "7/15 comparisons" with progress bar
  - Tests: `web/frontend/src/components/__tests__/SessionProgress.test.tsx`
    - Test progress percentage calculation
    - Test completion state
  - Acceptance: Progress displays correctly

#### 3.5 ComparisonView Container
- [ ] Create main comparison view
  - Files: `web/frontend/src/components/ComparisonView.tsx` (new)
  - Responsibilities:
    - Fetch session on mount
    - Display two TrackCard components (stacked)
    - Display SessionProgress
    - Handle loading and error states
  - Tests: `web/frontend/src/components/__tests__/ComparisonView.test.tsx`
    - Test loading state
    - Test error state
    - Test successful render
  - Acceptance: View displays comparison pair

#### 3.6 App Root Component
- [ ] Set up React Query provider and routing
  - Files: `web/frontend/src/App.tsx` (modify)
  - Setup:
    - QueryClientProvider
    - ComparisonView as main component
  - Tests: `web/frontend/src/__tests__/App.test.tsx`
    - Test app renders without errors
  - Acceptance: App loads and displays comparison view

### Phase 4: Waveform & Audio Playback

#### 4.1 Wavesurfer Hook
- [ ] Create wavesurfer.js integration hook
  - Files: `web/frontend/src/hooks/useWavesurfer.ts` (new)
  - Hook: `useWavesurfer({ trackId, onReady, onSeek })`
  - Responsibilities:
    - Create WaveSurfer instance
    - Load pre-computed peaks from `/api/tracks/{id}/waveform`
    - Load audio from `/api/tracks/{id}/stream`
    - Expose: `containerRef`, `isPlaying`, `currentTime`, `duration`, `seekToPercent()`, `togglePlayPause()`
  - Cleanup: Destroy instance on unmount
  - Tests: `web/frontend/src/hooks/__tests__/useWavesurfer.test.ts`
    - Test instance creation
    - Test cleanup on unmount
    - Mock WaveSurfer API
  - Acceptance: Wavesurfer instance manages audio correctly

#### 4.2 WaveformPlayer Component
- [ ] Create waveform visualization component
  - Files: `web/frontend/src/components/WaveformPlayer.tsx` (new)
  - Props: `trackId: number`, `onSeek?: (percent) => void`
  - Uses: `useWavesurfer()` hook
  - Display:
    - Waveform visualization (80px height)
    - Current time / Duration
    - Play/pause button (optional, can use track card tap)
  - Styling: Responsive, mobile-optimized
  - Tests: `web/frontend/src/components/__tests__/WaveformPlayer.test.tsx`
    - Test waveform renders
    - Test play/pause toggle
    - Test seeking
  - Acceptance: Waveform displays and seeking works

#### 4.3 Audio Playback State
- [ ] Integrate audio playback with Zustand store
  - Files: `web/frontend/src/stores/comparisonStore.ts` (modify)
  - Add:
    - `setPlaying(trackId)` - Sets active track, pauses others
  - Files: `web/frontend/src/hooks/useAudioPlayer.ts` (new)
  - Hook: `useAudioPlayer(trackId)` - Syncs with store
  - Tests: `web/frontend/src/hooks/__tests__/useAudioPlayer.test.ts`
    - Test only one track plays at a time
    - Test switching tracks pauses previous
  - Acceptance: Audio playback mutually exclusive

#### 4.4 QuickSeekBar Component
- [ ] Create quick seek button bar
  - Files: `web/frontend/src/components/QuickSeekBar.tsx` (new)
  - Props: `onSeek: (percent) => void`, `currentPercent: number`
  - Display: Buttons [1][2][3][4][5][6][7][8][9] for 10%-90%
  - Keyboard: Listen for number key presses (1-9)
  - Styling: Highlight current position
  - Tests: `web/frontend/src/components/__tests__/QuickSeekBar.test.tsx`
    - Test button clicks call onSeek
    - Test keyboard events call onSeek
    - Test current position highlight
  - Acceptance: Quick seek works via buttons and keyboard

### Phase 5: Gesture Handling

#### 5.1 Swipe Gesture Hook
- [ ] Create swipe detection hook
  - Files: `web/frontend/src/hooks/useSwipeGesture.ts` (new)
  - Hook: `useSwipeGesture({ onSwipeRight, onSwipeLeft, onTap })`
  - Uses: `@use-gesture/react`
  - Thresholds:
    - Swipe distance: 100px
    - Velocity: 0.5
  - Returns: `bind()` function for gesture binding
  - Tests: `web/frontend/src/hooks/__tests__/useSwipeGesture.test.ts`
    - Test swipe right triggers callback
    - Test swipe left triggers callback
    - Test tap triggers callback
    - Mock gesture events
  - Acceptance: Gestures detect correctly

#### 5.2 SwipeableTrack Component
- [ ] Create swipeable track card wrapper
  - Files: `web/frontend/src/components/SwipeableTrack.tsx` (new)
  - Props:
    - `track: Track`
    - `onSwipeRight: () => void` (mark winner)
    - `onSwipeLeft: () => void` (archive)
    - `onTap: () => void` (play)
  - Uses:
    - `useSwipeGesture()` hook
    - `react-spring` for animations
  - Behavior:
    - Drag: Card follows finger
    - Release: Card snaps back or commits action
    - Visual feedback: Show 🏆 icon on right swipe, 📦 on left
  - Tests: `web/frontend/src/components/__tests__/SwipeableTrack.test.tsx`
    - Test swipe animations
    - Test action callbacks
  - Acceptance: Swipe gestures work smoothly

#### 5.3 Integrate Gestures into ComparisonView
- [ ] Connect swipe actions to API calls
  - Files: `web/frontend/src/components/ComparisonView.tsx` (modify)
  - Actions:
    - Swipe right on Track A → `recordComparison(track_a.id)` → load next pair
    - Swipe left on Track B → `archiveTrack(track_b.id)` → load next pair
    - Tap Track A → `setPlaying(track_a.id)`
  - Handle loading states during API calls
  - Tests: `web/frontend/src/components/__tests__/ComparisonView.test.tsx` (add)
    - Test swipe right records comparison
    - Test swipe left archives track
    - Test next pair loads after action
  - Acceptance: Full comparison flow works end-to-end

### Phase 6: Polish & Error Handling

#### 6.1 Loading States
- [ ] Add skeleton loaders
  - Files:
    - `web/frontend/src/components/TrackCardSkeleton.tsx` (new)
    - `web/frontend/src/components/WaveformSkeleton.tsx` (new)
  - Display: Animated skeleton during data fetch
  - Tests: Visual testing only
  - Acceptance: Loading states look polished

#### 6.2 Error Handling
- [ ] Add error states and toasts
  - Files: `web/frontend/src/components/ErrorState.tsx` (new)
  - Display:
    - Network errors: "Connection lost" with retry button
    - No tracks: "No tracks available for comparison"
    - Waveform generation failure: Fallback to basic player
  - Tests: `web/frontend/src/components/__tests__/ErrorState.test.tsx`
    - Test error messages display
    - Test retry button works
  - Acceptance: Errors handled gracefully

#### 6.3 Mobile Optimizations
- [ ] Add mobile-specific styles and meta tags
  - Files:
    - `web/frontend/index.html` (modify) - Add viewport meta tag
    - `web/frontend/src/styles/index.css` (modify)
  - Optimizations:
    - `touch-action: manipulation` on buttons (prevent double-tap zoom)
    - Min touch target 44x44px
    - `-webkit-overflow-scrolling: touch`
    - Prevent body scroll during swipe
  - Tests: Manual testing on phone
  - Acceptance: UI feels native on mobile

#### 6.4 Session Completion
- [ ] Add session completion screen
  - Files: `web/frontend/src/components/SessionComplete.tsx` (new)
  - Display:
    - "15 comparisons completed!"
    - Summary stats (if available)
    - "Start new session" button
  - Tests: `web/frontend/src/components/__tests__/SessionComplete.test.tsx`
    - Test renders with correct stats
    - Test button starts new session
  - Acceptance: Completion screen displays after target reached

## Acceptance Criteria

### Functional Requirements
- [ ] User can start comparison session from phone browser
- [ ] User can play both tracks with instant switching
- [ ] Waveform displays instantly (pre-computed peaks)
- [ ] User can seek by tapping waveform
- [ ] User can quick-seek with number keys (1-9)
- [ ] Swipe right records comparison and loads next pair
- [ ] Swipe left archives track
- [ ] Session completes after target comparisons
- [ ] All comparisons appear in CLI history (`/rate comparisons`)
- [ ] Ratings update in database (verified via CLI `/rankings`)

### Technical Requirements
- [ ] All TypeScript compiles without errors
- [ ] Backend tests pass (`uv run pytest web/backend/tests/`)
- [ ] Frontend tests pass (`npm test`)
- [ ] No console errors in browser
- [ ] Works on Chrome/Safari mobile
- [ ] API endpoints documented (FastAPI auto-docs)

### Performance Requirements
- [ ] Waveform loads in <200ms (cached)
- [ ] Audio starts playing in <500ms
- [ ] Swipe gestures feel responsive (60fps)
- [ ] No UI blocking during API calls

### Quality Requirements
- [ ] Code follows functional programming style (pure functions)
- [ ] No `any` types in TypeScript
- [ ] Backend follows existing patterns from `domain/rating/`
- [ ] Ruff formatting applied to Python code

## Files to Create/Modify

### Backend (New Files)
- `web/backend/__init__.py`
- `web/backend/main.py`
- `web/backend/routers/__init__.py`
- `web/backend/routers/comparisons.py`
- `web/backend/routers/tracks.py`
- `web/backend/schemas.py`
- `web/backend/waveform.py`
- `web/backend/deps.py`
- `web/backend/tests/test_main.py`
- `web/backend/tests/test_schemas.py`
- `web/backend/tests/test_comparisons.py`
- `web/backend/tests/test_tracks.py`
- `web/backend/tests/test_waveform.py`

### Backend (Modified Files)
- `pyproject.toml` - Add web dependencies

### Frontend (New Files)
- `web/frontend/package.json`
- `web/frontend/vite.config.ts`
- `web/frontend/tailwind.config.js`
- `web/frontend/tsconfig.json`
- `web/frontend/index.html`
- `web/frontend/src/main.tsx`
- `web/frontend/src/App.tsx`
- `web/frontend/src/types/index.ts`
- `web/frontend/src/api/client.ts`
- `web/frontend/src/api/comparisons.ts`
- `web/frontend/src/api/tracks.ts`
- `web/frontend/src/stores/comparisonStore.ts`
- `web/frontend/src/hooks/useComparison.ts`
- `web/frontend/src/hooks/useWavesurfer.ts`
- `web/frontend/src/hooks/useSwipeGesture.ts`
- `web/frontend/src/hooks/useAudioPlayer.ts`
- `web/frontend/src/components/ComparisonView.tsx`
- `web/frontend/src/components/TrackCard.tsx`
- `web/frontend/src/components/SwipeableTrack.tsx`
- `web/frontend/src/components/WaveformPlayer.tsx`
- `web/frontend/src/components/QuickSeekBar.tsx`
- `web/frontend/src/components/SessionProgress.tsx`
- `web/frontend/src/components/SessionComplete.tsx`
- `web/frontend/src/components/TrackCardSkeleton.tsx`
- `web/frontend/src/components/WaveformSkeleton.tsx`
- `web/frontend/src/components/ErrorState.tsx`
- `web/frontend/src/styles/index.css`

### Frontend (Test Files)
- `web/frontend/src/__tests__/App.test.tsx`
- `web/frontend/src/api/__tests__/client.test.ts`
- `web/frontend/src/stores/__tests__/comparisonStore.test.ts`
- `web/frontend/src/hooks/__tests__/useComparison.test.ts`
- `web/frontend/src/hooks/__tests__/useWavesurfer.test.ts`
- `web/frontend/src/hooks/__tests__/useSwipeGesture.test.ts`
- `web/frontend/src/hooks/__tests__/useAudioPlayer.test.ts`
- `web/frontend/src/components/__tests__/TrackCard.test.tsx`
- `web/frontend/src/components/__tests__/ComparisonView.test.tsx`
- `web/frontend/src/components/__tests__/SwipeableTrack.test.tsx`
- `web/frontend/src/components/__tests__/WaveformPlayer.test.tsx`
- `web/frontend/src/components/__tests__/QuickSeekBar.test.tsx`
- `web/frontend/src/components/__tests__/SessionProgress.test.tsx`
- `web/frontend/src/components/__tests__/SessionComplete.test.tsx`
- `web/frontend/src/components/__tests__/ErrorState.test.tsx`

### Existing Files (Reference Only - Do Not Modify)
- `src/music_minion/domain/rating/elo.py` - ELO algorithm functions to reuse
- `src/music_minion/domain/rating/database.py` - Database operations to import
- `src/music_minion/core/database.py` - Database connection utilities

## Dependencies

### System Dependencies
- **audiowaveform** (required for waveform generation)
  - Ubuntu/Debian: `sudo apt install audiowaveform`
  - macOS: `brew install audiowaveform`
  - Arch: `sudo pacman -S audiowaveform`

### Python Dependencies (Added to pyproject.toml)
```toml
[project.optional-dependencies]
web = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "python-multipart>=0.0.6",
]
```

### Frontend Dependencies (package.json)
```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "wavesurfer.js": "^7.8.0",
    "@use-gesture/react": "^10.3.0",
    "@react-spring/web": "^9.7.0",
    "@tanstack/react-query": "^5.51.0",
    "zustand": "^4.5.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.3.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",
    "typescript": "^5.5.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "vitest": "^1.6.0",
    "@testing-library/react": "^16.0.0"
  }
}
```

## Task Dependencies

### Critical Path
1. **Phase 1.1-1.4** must complete before any other backend work
2. **Phase 1.5** (comparison endpoints) depends on 1.1-1.4
3. **Phase 1.7** (waveform) depends on 1.1-1.4 but can run parallel to 1.5-1.6
4. **Phase 2.1-2.3** must complete before any frontend component work
5. **Phase 2.4-2.5** depends on 2.1-2.3 and Phase 1.2 (schemas)
6. **Phase 3** depends on Phase 2 completion
7. **Phase 4** depends on Phase 3 completion
8. **Phase 5** depends on Phase 3 completion (can run parallel to Phase 4)
9. **Phase 6** is final polish, depends on all previous phases

### Parallelizable Work
- Backend routes (1.5, 1.6, 1.7) can be developed in parallel after 1.1-1.4
- Frontend components (3.3, 3.4) can be developed in parallel after 3.1-3.2
- Waveform integration (4.1-4.2) and gesture handling (5.1-5.2) can run in parallel

## Development Commands

### Backend Development
```bash
# Install dependencies
uv sync --extra web

# Run backend server
cd web/backend
uv run uvicorn main:app --reload --port 8000

# Run backend tests
uv run pytest web/backend/tests/
```

### Frontend Development
```bash
# Install dependencies
cd web/frontend
npm install

# Run dev server
npm run dev

# Run tests
npm test

# Build for production
npm run build
```

### Production Deployment
```bash
# Build frontend
cd web/frontend && npm run build

# Run combined server (serves static + API)
cd ../..
uv run uvicorn web.backend.main:app --host 0.0.0.0 --port 8000
```

## Testing Strategy

### Backend Testing
- Unit tests for all endpoints
- Integration tests for database operations
- Mock external dependencies (database, filesystem)
- Test error cases (404, invalid input, etc.)

### Frontend Testing
- Component tests with React Testing Library
- Hook tests with renderHook
- Mock API calls with MSW (Mock Service Worker)
- Test gesture interactions
- Test loading and error states

### Manual Testing Checklist
- [ ] Test on Chrome mobile
- [ ] Test on Safari mobile
- [ ] Test swipe gestures feel responsive
- [ ] Test audio playback quality
- [ ] Test waveform seeking accuracy
- [ ] Test session completion flow
- [ ] Verify comparisons in CLI (`/rate comparisons`)
- [ ] Verify ratings in CLI (`/rankings`)

## Notes for Implementation

### Code Style Requirements
- **Python**: Follow existing patterns in `src/music_minion/domain/rating/`
- **Python**: Use Ruff formatting (`uv run ruff format`)
- **Python**: Type hints required for all functions
- **TypeScript**: No `any` types, explicit return types
- **Functional style**: Pure functions preferred, avoid classes
- **Immutability**: Use `dataclasses.replace()` in Python, immutable state in React

### Critical Patterns to Follow

#### Python: Reuse Domain Logic
```python
# GOOD: Import and reuse existing functions
from music_minion.domain.rating.elo import select_strategic_pair
from music_minion.domain.rating.database import record_comparison

# BAD: Reimplementing ELO logic
def my_select_pair():  # Don't do this!
    ...
```

#### TypeScript: Type Safety
```typescript
// GOOD: Explicit types
const startSession = async (options: StartSessionRequest): Promise<StartSessionResponse> => {
  ...
}

// BAD: Implicit any
const startSession = async (options) => {  // Don't do this!
  ...
}
```

#### React: Pure Components
```typescript
// GOOD: Pure functional component
export function TrackCard({ track, isPlaying }: TrackCardProps) {
  return <div>...</div>
}

// BAD: Class component
class TrackCard extends React.Component {  // Don't do this!
  ...
}
```
