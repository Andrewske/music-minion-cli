# Personal Radio Station Implementation

## Overview

A 24/7 personal radio station built as an extension to music-minion. Streams audio via Icecast with a web UI for schedule management and a separate video page for YouTube content.

**Core concept:** Define multiple stations with schedules, but only one streams at a time. Each station has a "virtual timeline" - when you switch stations, it calculates where that station would be and starts from there.

### Goals

1. **Zero decision fatigue** - Turn it on, music plays, no choices required
2. **Always-running feel** - Tune in mid-song like real radio
3. **Multi-device** - Stream to phone, speakers, anywhere
4. **Schedule-driven** - Different content for different times of day
5. **Override-friendly** - Change schedule, stream updates immediately

## Task Sequence

Execute these tasks in numerical order. Each task builds on previous ones.

### Phase 0: Foundation
1. [01-postgresql-migration.md](./01-postgresql-migration.md) - **Migrate from SQLite to PostgreSQL**
   - Enables Desktop and Pi to share ratings, ELO, playlists
   - Add DATABASE_URL environment variable support
   - Create migration script for one-time data transfer
   - Test bidirectional sync between instances

### Phase 1: Core Radio Backend
2. [02-radio-data-model.md](./02-radio-data-model.md) - **Add radio database tables**
   - Create stations, station_schedule, radio_history tables
   - Add daily_schedule table for pre-computed schedules
   - Define domain models (Station, ScheduledTrack, NowPlaying)

3. [03-station-crud-and-schedule-builder.md](./03-station-crud-and-schedule-builder.md) - **Station management and schedule builder**
   - Implement station CRUD operations
   - Build nightly schedule generator with boundary-aware track selection
   - Handle time ranges, shuffle/queue modes
   - Swap long tracks near boundaries to avoid >5 min overshoot

4. [04-liquidsoap-scheduler-integration.md](./04-liquidsoap-scheduler-integration.md) - **Audio streaming pipeline**
   - Create HTTP endpoint for Liquidsoap to poll (`/api/radio/next-track`)
   - Implement ffmpeg seeking for mid-track tune-in
   - Configure Liquidsoap with crossfade and Icecast output
   - Handle YouTube/SoundCloud via yt-dlp protocol

### Phase 2: Web Interface
5. [05-web-ui-backend-endpoints.md](./05-web-ui-backend-endpoints.md) - **FastAPI endpoints**
   - Station management endpoints (list, create, activate)
   - Schedule editor endpoints (add/update/delete time ranges)
   - Now-playing and history endpoints
   - WebSocket for real-time updates

6. [06-web-ui-frontend.md](./06-web-ui-frontend.md) - **React UI components**
   - Main radio page with now-playing display
   - Schedule editor for time ranges
   - Station selector dropdown
   - Video page with YouTube embed
   - WebSocket hook for live updates

### Phase 3: Deployment
7. [07-docker-deployment.md](./07-docker-deployment.md) - **Docker Compose for Raspberry Pi**
   - Complete docker-compose.yml with all services
   - Icecast, Liquidsoap, FastAPI, React, Caddy
   - HTTPS reverse proxy with Let's Encrypt
   - Deployment instructions and environment setup

## Success Criteria

### Functional Requirements
- [ ] Desktop and Pi share PostgreSQL database for ratings, ELO, playlists
- [ ] Radio stations can be created with shuffle or queue mode
- [ ] Meta-station (Main) references other stations via time ranges
- [ ] Daily schedule is pre-computed nightly with boundary-aware track selection
- [ ] Icecast streams 24/7 at `http://mm.kevinandrews.info/stream`
- [ ] Web UI displays now-playing with progress bar and upcoming queue
- [ ] Schedule editor allows adding/removing time ranges with 2s debounce
- [ ] YouTube video page embeds player when video content is scheduled
- [ ] Load gaps (~3s) for YouTube/SoundCloud built into schedule

### Non-Functional Requirements
- [ ] All services auto-restart on crash (`restart: unless-stopped`)
- [ ] Liquidsoap uses youtube-dl protocol for YouTube and SoundCloud
- [ ] Seeking works correctly for mid-track tune-in via ffmpeg
- [ ] Playback logged to radio_history table
- [ ] WebSocket updates frontend every 5 seconds
- [ ] HTTPS enabled via Caddy with automatic cert renewal

## Execution Instructions

1. **Execute tasks in numerical order** (01 → 07)
2. Each task file contains:
   - Files to modify/create
   - Implementation details with code samples
   - Acceptance criteria
   - Dependencies on previous tasks
   - Testing strategies

3. **Verify acceptance criteria** before moving to next task
4. **Run tests** after each task to ensure nothing breaks

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Hosted PostgreSQL                             │
│  (tracks, ratings, elo_ratings, playlists, stations, radio_*)       │
└─────────────────────────────────────────────────────────────────────┘
                    ▲                           ▲
                    │                           │
       ┌────────────┴────────────┐   ┌─────────┴──────────────────────┐
       │    Desktop (CLI)         │   │   Raspberry Pi (Radio)         │
       │  - Local playback (MPV)  │   │  ┌──────────────────────────┐ │
       │  - Track comparison      │   │  │   Docker Compose:        │ │
       │  - Metadata editing      │   │  │  - Liquidsoap → Icecast  │ │
       └──────────────────────────┘   │  │  - FastAPI Backend       │ │
                    │                 │  │  - React Frontend        │ │
                    ▼                 │  │  - Caddy (HTTPS)         │ │
       ┌────────────────────────────┐ │  └──────────────────────────┘ │
       │      Syncthing             │◀┼──────────────────────────────┘ │
       │  (Opus audio files)        │ │                                │
       └────────────────────────────┘ └────────────────────────────────┘
```

## Dependencies

### External Services
- Hosted PostgreSQL database (for shared state)
- Domain name pointing to Pi IP (mm.kevinandrews.info)
- Cloudflare API token (optional, for HTTPS DNS challenge)

### Software Requirements
- Docker and Docker Compose (on Pi)
- Syncthing (for audio file sync between Desktop and Pi)
- PostgreSQL client libraries (psycopg)

### New Python Dependencies
```toml
# pyproject.toml additions
dependencies = [
    "psycopg[binary,pool]>=3.1.0",  # PostgreSQL adapter
]
```

### New JavaScript Dependencies
```json
// web/frontend/package.json additions
{
  "dependencies": {
    "react-youtube": "^10.1.0"  // YouTube embed component
  }
}
```

## Data Flow

1. **Desktop edits metadata** → Saves to audio file Vorbis comments → Syncthing syncs → Pi re-imports
2. **Desktop adds rating** → PostgreSQL → Pi sees immediately
3. **Pi builds schedule** → Nightly cron at midnight → Pre-computes full day with boundary logic
4. **Liquidsoap polls** → `/api/radio/next-track` → Scheduler returns URI + seek info
5. **Web UI updates** → WebSocket pushes now-playing every 5s → React updates display

## Technical Decisions

### Why PostgreSQL over SQLite?
- Desktop and Pi need shared access to ratings, ELO, schedules
- SQLite doesn't support concurrent network access
- Hosted PostgreSQL enables true multi-device sync

### Why pre-compute daily schedule?
- Avoids runtime complexity of boundary checking
- Globally optimal track selection with full day context
- Simpler Liquidsoap integration (just query schedule)
- 3-second load gaps baked in for YouTube/SoundCloud

### Why Liquidsoap over custom streaming?
- Battle-tested audio engine with crossfade support
- Built-in youtube-dl protocol for remote sources
- Native Icecast integration
- Mature ecosystem

## Troubleshooting

### Radio goes silent
1. Check Liquidsoap logs: `docker compose logs liquidsoap`
2. Verify backend is responding: `curl http://localhost:8001/api/radio/next-track`
3. Check Icecast status: `http://localhost:8000/status.xsl`
4. Restart services: `docker compose restart`

### Desktop changes not visible on Pi
1. Verify DATABASE_URL is same on both instances
2. Check PostgreSQL connection: `psql $DATABASE_URL -c "\dt"`
3. Test write from Desktop, read from Pi

### Schedule doesn't rebuild
1. Check cron job is running
2. Manually trigger: `curl -X POST http://localhost:8001/api/radio/stations/1/activate`
3. Check logs for errors

## Future Enhancements (Post-V1)

Not in scope for initial implementation:

- AI DJ personality with TTS clips
- Time-shifted listening (Radio DVR)
- Reactive scheduling based on weather/calendar
- Collaborative stations with friends
- Podcast support via RSS feeds
- Mobile app (PWA sufficient for v1)

## Resources

- [Liquidsoap Documentation](https://www.liquidsoap.info/doc-dev/)
- [Icecast Documentation](https://icecast.org/docs/)
- [PostgreSQL Connection Pooling](https://www.psycopg.org/psycopg3/docs/advanced/pool.html)
- [Opus Codec](https://opus-codec.org/)
