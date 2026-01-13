# Personal Radio Deployment Status

## Deployment Complete

**Stream URL**: http://46.62.221.136:8080/stream
**Web UI**: http://46.62.221.136:8080
**API**: http://46.62.221.136:8080/api/radio/

### What's Running

| Container | Status | Description |
|-----------|--------|-------------|
| radio-caddy | Running | Reverse proxy on port 8080 |
| radio-backend | Running | FastAPI server |
| radio-icecast | Running | Streaming server (Opus) |
| radio-liquidsoap | Running | Audio engine |

### Configuration

```
DOMAIN=mm.kevinandrews.info
MUSIC_PATH=/root/music
DATABASE_URL=postgresql://Kevin:***@postgresql-182781-0.cloudclusters.net:10010/music-minion
```

### Database Stats

- Tracks: 23,032
- Playlists: 345
- Playlist Tracks: 15,745
- Stations: 1 (Local Radio - 805 tracks)

## Implementation Details

### Phase 1: Core Radio Implementation (Complete)

**Database (SQLite v27 migration)**
- Added tables: `stations`, `station_schedule`, `radio_history`, `radio_state`, `radio_skipped`
- File: `src/music_minion/core/database.py`

**Domain Logic**
- `src/music_minion/domain/radio/models.py` - Station, ScheduleEntry, NowPlaying dataclasses
- `src/music_minion/domain/radio/stations.py` - Station CRUD operations
- `src/music_minion/domain/radio/schedule.py` - Time range schedule management
- `src/music_minion/domain/radio/timeline.py` - Deterministic timeline calculation
- `src/music_minion/domain/radio/scheduler.py` - Service that feeds tracks to Liquidsoap

**FastAPI Backend**
- `web/backend/routers/radio.py` - All radio API endpoints
- `GET /api/radio/next-track` - Plain text file path for Liquidsoap
- `GET /api/radio/now-playing` - Current playback state
- Full CRUD for stations and schedules

**React Frontend**
- `web/frontend/src/api/radio.ts` - API client
- `web/frontend/src/components/RadioPage.tsx` - Main layout
- `web/frontend/src/components/RadioPlayer.tsx` - Now playing with progress bar
- `web/frontend/src/components/UpNext.tsx` - Upcoming tracks list
- `web/frontend/src/components/StationsList.tsx` - Station switcher

**Docker Infrastructure**
- `docker/radio/docker-compose.yml` - Local dev setup
- `docker/radio/docker-compose.prod.yml` - Production setup with Caddy
- `docker/radio/icecast/Dockerfile` - ARM64-compatible Icecast build
- `docker/radio/liquidsoap/` - Liquidsoap with crossfade, normalization
- `docker/radio/Caddyfile` - Reverse proxy config
- `docker/radio/backend.Dockerfile` - FastAPI container

### PostgreSQL Support (Complete)

**Database Adapter**
- `src/music_minion/core/db_adapter.py` - Supports both SQLite and PostgreSQL
- Auto-detects based on `DATABASE_URL` environment variable
- Converts SQLite `?` placeholders to PostgreSQL `%s`

**Import Script**
- `docker/radio/import_tracks.py` - Imports from SQLite to PostgreSQL
- Handles NUL character sanitization
- Boolean casting for PostgreSQL compatibility

## Issues Resolved

1. **Caddyfile routing** - `try_files` was catching API requests before proxy; fixed by wrapping static file handling in its own `handle` block.

2. **Track path mismatch** - Database has paths like `/home/kevin/Music/radio-library/...` but server files at `/root/music`. Fixed by mounting music at the expected path in containers.

3. **PostgreSQL boolean type** - SQLite stores booleans as 0/1 integers; fixed import script to cast to Python bool.

4. **HTTP timeout** - Liquidsoap's 10s timeout was too short for remote PostgreSQL queries; increased to 30s.

## Quick Commands

```bash
# SSH to server
ssh root@46.62.221.136

# Check container status
docker ps --filter 'name=radio'

# View backend logs
docker logs radio-backend -f

# View liquidsoap logs
docker logs radio-liquidsoap -f

# Restart all radio services
cd /root/docker/radio
docker compose -f docker-compose.prod.yml restart

# Test APIs
curl http://46.62.221.136:8080/api/radio/stations
curl http://46.62.221.136:8080/api/radio/now-playing
curl http://46.62.221.136:8080/api/radio/next-track
```

## Future Improvements

- [ ] DNS setup: Point `mm.kevinandrews.info` to server
- [ ] HTTPS: Update Caddy for Let's Encrypt
- [ ] Skip/love functionality from web UI
- [ ] Schedule editor UI
