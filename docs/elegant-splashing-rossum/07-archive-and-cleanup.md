---
task: 07-archive-and-cleanup
status: pending
depends: [06-home-page]
files:
  - path: docs/archive/radio-stack/README.md
    action: create
  - path: web/frontend/src/stores/radioStore.ts
    action: delete
  - path: web/frontend/src/components/RadioPlayer.tsx
    action: delete
  - path: web/frontend/src/components/RadioPage.tsx
    action: delete
  - path: web/backend/routers/radio.py
    action: delete
  - path: CLAUDE.md
    action: modify
---

# Archive & Cleanup

## Context
Final cleanup phase. Archives the radio stack code for potential future revival, deletes deprecated files, and updates documentation. This should only be done after verifying the new player works correctly.

## Files to Modify/Create
- `docs/archive/radio-stack/README.md` (new)
- `docs/archive/radio-stack/` (copy radio files here)
- Delete deprecated files (listed below)
- `CLAUDE.md` (modify - update documentation)

## Implementation Details

### 1. Archive to `docs/archive/radio-stack/`:

Create directory and copy:

```bash
mkdir -p docs/archive/radio-stack
cp -r docker/radio docs/archive/radio-stack/docker-radio
cp web/backend/routers/radio.py docs/archive/radio-stack/radio_router.py
cp web/frontend/src/stores/radioStore.ts docs/archive/radio-stack/radioStore.ts
cp web/frontend/src/components/RadioPlayer.tsx docs/archive/radio-stack/RadioPlayer.tsx
cp web/frontend/src/components/RadioPage.tsx docs/archive/radio-stack/RadioPage.tsx
```

### 2. Create `docs/archive/radio-stack/README.md`:

```markdown
# Radio Stack Archive

Archived on: YYYY-MM-DD

## What This Was

An always-on radio streaming setup using:
- **Icecast**: Audio stream server (port 8001)
- **Liquidsoap**: Audio player/orchestrator that requested tracks from backend

The backend scheduler would pick tracks based on station rules, Liquidsoap would
fetch and play them, streaming through Icecast to all connected clients.

## Why It Was Archived

Replaced with a simpler frontend-driven global player:
- Lower resource usage (no Docker containers needed)
- Simpler architecture (frontend controls playback directly)
- Cross-device control (Spotify Connect style)
- Same UX with less complexity

## How to Revive

1. Copy `docker-radio/` back to `docker/radio/`
2. Restore `radio_router.py` to `web/backend/routers/radio.py`
3. Add router to `web/backend/main.py`
4. Restore frontend components
5. Update `SCHEDULER_URL` env var in docker-compose to match backend port
6. Run: `cd docker/radio && docker compose up -d`

## Key Files

- `docker-radio/docker-compose.yml` - Service definitions
- `docker-radio/liquidsoap/radio.liq` - Liquidsoap script
- `docker-radio/icecast.xml` - Icecast configuration
- `radio_router.py` - Backend API endpoints
- `radioStore.ts` - Frontend state management
- `RadioPlayer.tsx` - Stream player component
- `RadioPage.tsx` - Radio page layout
```

### 3. Delete deprecated files:

```bash
# Frontend
rm web/frontend/src/stores/radioStore.ts
rm web/frontend/src/components/RadioPlayer.tsx
rm web/frontend/src/components/RadioPage.tsx

# Backend (after archiving)
rm web/backend/routers/radio.py

# Docker (after archiving)
rm -rf docker/radio
```

### 4. Remove radio router from `web/backend/main.py`:

```python
# Remove this line:
# from routers import radio
# app.include_router(radio.router, prefix="/api/radio", tags=["radio"])
```

### 5. Update `CLAUDE.md`:

Remove radio/Liquidsoap documentation sections:
- Remove "Personal Radio (Docker)" section
- Remove radio-related commands
- Remove Liquidsoap debugging instructions

Add global player documentation:
```markdown
## Global Player

Frontend-driven player with cross-device control:
- **playerStore**: Zustand store for playback state
- **PlayerBar**: Persistent bottom bar with controls
- **Cross-device sync**: WebSocket broadcasts state to all connected devices

Key files:
- `web/frontend/src/stores/playerStore.ts`
- `web/frontend/src/components/player/PlayerBar.tsx`
- `web/backend/routers/player.py`

Commands:
- Player API: `http://localhost:8642/api/player/`
- Device list: `GET /api/player/devices`
- Current state: `GET /api/player/state`
```

### 6. Clean up any remaining references:

Search for and remove any remaining references to:
- `radioStore`
- `RadioPlayer`
- `RadioPage`
- `/api/radio/`
- Liquidsoap
- Icecast

```bash
grep -r "radioStore\|RadioPlayer\|RadioPage\|/api/radio\|liquidsoap\|icecast" web/frontend/src --include="*.ts" --include="*.tsx"
```

## Verification

1. Verify archive directory exists with all files: `ls -la docs/archive/radio-stack/`
2. Verify deprecated files are deleted
3. Verify app still works without radio code:
   - `uv run music-minion --web`
   - Play a track, verify it works
4. Verify no remaining references to radio code: `grep -r "radioStore" web/`
5. Verify CLAUDE.md is updated
6. Run any existing tests to ensure nothing breaks
