# Mobile Web UI for ELO Track Comparisons - Implementation Plan

## Overview

Add a mobile-first web interface to Music Minion for ELO track comparisons accessible from phone browser. Enables rating tracks away from home with waveform seeking, gesture-based voting, and audio streaming.

## Architecture

```
┌─────────────────────────────────────────┐
│  Phone Browser (via Tailscale)          │
│  ┌───────────────────────────────────┐  │
│  │  React + Vite Frontend            │  │
│  │  - Track cards (swipe gestures)   │  │
│  │  - wavesurfer.js waveform         │  │
│  │  - Audio playback                 │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
           │ HTTP/WebSocket
           ▼
┌─────────────────────────────────────────┐
│  Server (home machine)                   │
│  ┌───────────────────────────────────┐  │
│  │  FastAPI Backend                  │  │
│  │  - Reuses domain/rating modules   │  │
│  │  - Audio streaming                │  │
│  │  - Waveform generation            │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │  SQLite (existing)                │  │
│  │  - tracks, elo_ratings, history   │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │  Local Audio Files                │  │
│  │  - MP3, M4A, Opus                 │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## UX Design

### Mobile Layout (Single Screen)

```
┌─────────────────────────────────────┐
│  Session: 7/15 comparisons          │
├─────────────────────────────────────┤
│  ┌───────────────────────────────┐  │
│  │ 🎵 Track A                    │  │
│  │ Artist Name - Title           │  │
│  │ Album • 2024 • 128 BPM        │  │
│  │ ⭐ 1547 (12 comparisons)      │  │
│  │ ← Archive    ▶ PLAYING  Win → │  │
│  └───────────────────────────────┘  │
│  [Swipe right = winner]             │
│  [Swipe left = archive]             │
│  [Tap = play this track]            │
├─────────────────────────────────────┤
│  ┌───────────────────────────────┐  │
│  │ 🎵 Track B                    │  │
│  │ Artist Name - Title           │  │
│  │ Album • 2025 • 140 BPM        │  │
│  │ ⚠️ 1489 (8 comparisons)       │  │
│  │ ← Archive            Winner → │  │
│  └───────────────────────────────┘  │
│  [Tap to play]                      │
├─────────────────────────────────────┤
│  ▁▂▃▅▆▇█▇▆▅▃▂▁▂▃▅▆█▇▅▃▂▁         │
│  [Waveform - tap/drag to seek]      │
│  0:45 ━━━━━━━━━━●───── 3:22        │
├─────────────────────────────────────┤
│  [1][2][3][4][5][6][7][8][9]        │
│  Quick seek: 10% - 90%              │
└─────────────────────────────────────┘
```

### Gesture Interactions

- **Tap card**: Play that track (auto-pauses other)
- **Swipe card right**: Mark as winner → record comparison → load next pair
- **Swipe card left**: Archive track → load next pair
- **Tap waveform**: Seek to position
- **Number keys 1-9**: Jump to 10%-90% of track
- **Visual feedback**: Card slides during swipe, shows 🏆 or 📦 icon

## File Structure

```
music-minion-cli/
├── web/
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app
│   │   ├── routers/
│   │   │   ├── comparisons.py       # Session & comparison endpoints
│   │   │   └── tracks.py            # Streaming & waveform endpoints
│   │   ├── schemas.py               # Pydantic models
│   │   ├── waveform.py              # Waveform generation (audiowaveform CLI)
│   │   └── deps.py                  # FastAPI dependencies
│   └── frontend/
│       ├── package.json
│       ├── vite.config.ts
│       ├── tailwind.config.js
│       └── src/
│           ├── App.tsx              # Root component
│           ├── components/
│           │   ├── ComparisonView.tsx
│           │   ├── TrackCard.tsx
│           │   ├── SwipeableTrack.tsx
│           │   ├── WaveformPlayer.tsx
│           │   ├── QuickSeekBar.tsx
│           │   └── SessionProgress.tsx
│           ├── hooks/
│           │   ├── useComparison.ts
│           │   ├── useWavesurfer.ts
│           │   ├── useSwipeGesture.ts
│           │   └── useAudioPlayer.ts
│           ├── api/
│           │   ├── client.ts
│           │   ├── comparisons.ts
│           │   └── tracks.ts
│           ├── stores/
│           │   └── comparisonStore.ts
│           └── types/
│               └── index.ts
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/comparisons/session` | POST | Start new session with filters |
| `/api/comparisons/next-pair` | GET | Get next track pair |
| `/api/comparisons/record` | POST | Record winner, get next pair |
| `/api/tracks/{id}/archive` | POST | Archive track |
| `/api/tracks/{id}/stream` | GET | Stream audio (range support) |
| `/api/tracks/{id}/waveform` | GET | Get pre-computed waveform peaks |

## Key Technologies

### Backend
- **FastAPI**: Modern Python web framework
- **audiowaveform**: BBC tool for waveform peak generation
- **Existing domain logic**: Reuse `domain/rating/elo.py` and `domain/rating/database.py`

### Frontend
- **React + Vite**: Fast development, TypeScript support
- **wavesurfer.js**: Waveform visualization + seeking
- **@use-gesture/react**: Swipe detection
- **react-spring**: Smooth animations during swipe
- **React Query**: Server state management
- **Zustand**: Minimal UI state (playing track, session)
- **Tailwind CSS**: Mobile-first styling

## Implementation Phases

### Phase 1: Backend Foundation (Day 1)
- [ ] Create `web/backend/` structure
- [ ] FastAPI app with CORS for Vite dev server
- [ ] Session endpoints (start, get next pair) - reuse `select_strategic_pair()`
- [ ] Record comparison endpoint - reuse `record_comparison()`
- [ ] Audio streaming with range request support
- [ ] Test with curl/Postman

### Phase 2: Frontend Setup (Day 1-2)
- [ ] Vite + React + TypeScript project
- [ ] Tailwind CSS setup
- [ ] API proxy configuration
- [ ] TypeScript types from backend schemas
- [ ] API client with error handling

### Phase 3: Core UI (Day 2-3)
- [ ] TrackCard component (artist, title, album, year, BPM, rating)
- [ ] ComparisonView with two stacked cards
- [ ] SessionProgress indicator
- [ ] Start session + display first pair
- [ ] Basic layout (mobile-first)

### Phase 4: Waveform & Playback (Day 3-4)
- [ ] Waveform generation endpoint (audiowaveform CLI)
- [ ] Waveform caching in `~/.local/share/music-minion/waveforms/`
- [ ] wavesurfer.js integration
- [ ] WaveformPlayer component
- [ ] QuickSeekBar (1-9 buttons + keyboard)
- [ ] Audio playback state management

### Phase 5: Gestures (Day 4)
- [ ] @use-gesture/react setup
- [ ] SwipeableTrack wrapper
- [ ] Swipe right → record winner → next pair
- [ ] Swipe left → archive → next pair
- [ ] Tap → play/pause track
- [ ] Visual feedback (card animation, icons)

### Phase 6: Polish (Day 5)
- [ ] Loading skeletons
- [ ] Error states (no tracks, network errors)
- [ ] Session completion screen
- [ ] Mobile viewport optimizations
- [ ] Touch target sizes (min 44x44px)
- [ ] End-to-end flow testing

## Development Workflow

### Local Development

```bash
# Terminal 1: Backend (port 8000)
cd web/backend
uv run uvicorn main:app --reload

# Terminal 2: Frontend (port 5173)
cd web/frontend
npm run dev
```

### Production Build

```bash
# Build frontend
cd web/frontend
npm run build

# Run combined server
uv run music-minion-web --host 0.0.0.0 --port 8000
```

### Access via Tailscale

```bash
# Start server on home machine
music-minion-web

# Access from phone
https://<tailscale-hostname>:8000
```

## Waveform Generation

### Strategy: Pre-compute on-demand, cache forever

```python
# Uses BBC's audiowaveform CLI
audiowaveform -i track.mp3 -o track.json --pixels-per-second 50 -b 8

# Output: JSON with peaks array
{
  "version": 2,
  "channels": 2,
  "sample_rate": 44100,
  "samples_per_pixel": 882,
  "bits": 8,
  "length": 256,
  "data": [-45, 72, -38, 81, ...]  # Min/max peaks
}
```

### Caching
- Cache dir: `~/.local/share/music-minion/waveforms/`
- Filename: `{track_id}.json`
- Generation: On-demand (first request), then cached forever
- ~10KB per track (8-bit, 50 pixels/sec)

## MVP Scope

### Included in MVP
- ✅ Start comparison session with filters
- ✅ Two-track comparison with swipe gestures
- ✅ Waveform visualization with seeking
- ✅ Quick seek buttons (1-9)
- ✅ Audio streaming and playback
- ✅ Record comparisons (updates ELO ratings)
- ✅ Archive tracks
- ✅ Session progress tracking

### Deferred to Later
- ❌ Authentication (Tailscale-only access for MVP)
- ❌ Filter picker UI (use query params)
- ❌ Statistics/leaderboard view (use CLI)
- ❌ Comparison history viewer
- ❌ Undo last comparison
- ❌ Offline/PWA support
- ❌ Background waveform generation
- ❌ Real-time sync with CLI (both use same DB)
- ❌ Track metadata editing

## Dependencies

### Python (add to pyproject.toml)
```toml
[project.optional-dependencies]
web = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "python-multipart>=0.0.6",
]
```

### Frontend (package.json)
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
    "typescript": "^5.5.0"
  }
}
```

### System
```bash
# Install audiowaveform (for waveform generation)
# Ubuntu/Debian:
sudo apt install audiowaveform

# macOS:
brew install audiowaveform

# Arch:
sudo pacman -S audiowaveform
```

## Critical Implementation Details

### Reusing Existing Domain Logic

Backend imports directly from existing modules:

```python
from music_minion.domain.rating.elo import (
    select_strategic_pair,
    update_ratings,
    get_k_factor,
)
from music_minion.domain.rating.database import (
    get_or_create_rating,
    record_comparison,
    get_filtered_tracks,
)
from music_minion.core.database import get_db_connection
```

### Audio Streaming with Range Support

Critical for seeking:

```python
from fastapi.responses import FileResponse

@app.get("/api/tracks/{track_id}/stream")
async def stream_track(track_id: int):
    track = get_track_by_id(track_id)
    return FileResponse(
        track.file_path,
        media_type="audio/mpeg",
        headers={"Accept-Ranges": "bytes"}  # Enables seeking!
    )
```

### Swipe Gesture Thresholds

```typescript
const SWIPE_THRESHOLD = 100;  // 100px minimum swipe
const VELOCITY_THRESHOLD = 0.5;  // or fast flick

if (distance > SWIPE_THRESHOLD || velocity > VELOCITY_THRESHOLD) {
  // Commit action
}
```

### Mobile Optimizations

```css
/* Prevent double-tap zoom on buttons */
button {
  touch-action: manipulation;
}

/* Larger touch targets */
.track-card {
  min-height: 120px;
}

/* Smooth scrolling */
html {
  -webkit-overflow-scrolling: touch;
}
```

## Success Criteria

- [ ] Can start comparison session from phone browser
- [ ] Can play both tracks with instant switching
- [ ] Waveform displays instantly (pre-computed peaks)
- [ ] Can seek by tapping waveform or using number keys
- [ ] Swipe right records comparison and loads next pair
- [ ] Swipe left archives track
- [ ] Session completes after target comparisons
- [ ] All comparisons visible in CLI history (`/rate comparisons`)
- [ ] Ratings update in database (verified via CLI `/rankings`)

## Future Enhancements

- Real-time updates (WebSocket) when CLI records comparisons
- PWA for offline queueing
- Filter picker UI
- Comparison history viewer
- Leaderboard view
- Batch waveform generation CLI command
- Audio crossfade between tracks
- Playlist-specific comparison sessions with visual context
