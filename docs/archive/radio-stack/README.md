# Radio Stack Archive

Archived on: 2026-02-15

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
