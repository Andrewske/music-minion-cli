# Personal Radio Station Design

## Overview

A 24/7 personal radio station built as an extension to music-minion. Streams audio via Icecast, with a web UI for schedule management and a separate video page for YouTube content.

**Core concept:** Define multiple stations with schedules, but only one streams at a time. Each station has a "virtual timeline" - when you switch stations, it calculates where that station would be and starts from there.

## Goals

1. **Zero decision fatigue** - Turn it on, music plays, no choices required
2. **Always-running feel** - Tune in mid-song like real radio
3. **Multi-device** - Stream to phone, speakers, anywhere
4. **Schedule-driven** - Different content for different times of day
5. **Override-friendly** - Change schedule, stream updates immediately

## Non-Goals (v1)

- Skip functionality (it's radio)
- Server-side volume control (device handles this)
- Real-time sync between listeners (close enough is fine)
- Wake-up alarm (handled by Home Assistant automation)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     music-minion-radio                        │
│                   (new module in music-minion)                │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐    │
│  │   Station   │     │   Audio     │     │   Icecast   │    │
│  │  Scheduler  │────▶│   Engine    │────▶│   Server    │    │
│  │             │     │ (Liquidsoap)│     │             │    │
│  └─────────────┘     └─────────────┘     └─────────────┘    │
│         │                   ▲                   │            │
│         │                   │                   │            │
│         ▼                   │                   ▼            │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐    │
│  │   SQLite    │     │   Sources   │     │   Clients   │    │
│  │  (stations, │     │ - Local     │     │ - Web UI    │    │
│  │  schedules) │     │ - yt-dlp    │     │ - Phone     │    │
│  └─────────────┘     │ - librespot │     │ - HA Cast   │    │
│                      └─────────────┘     └─────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

### Components

- **Station Scheduler**: Calculates what should be playing based on station definition + current time. Tells Liquidsoap what to queue next.
- **Liquidsoap**: Audio engine handling crossfades, source switching, outputting to Icecast.
- **Icecast**: HTTP streaming server. Clients connect to stream URL.
- **Sources**: Local Opus files, YouTube (yt-dlp), Spotify (librespot), SoundCloud (stream URLs).

---

## Station Model

### Concept

**Stations are playlists with a mode.** This reuses music-minion's existing playlist architecture - a station is just a playlist with additional radio-specific metadata (shuffle/queue mode, whether it's active).

The "Main" station uses time ranges to reference other stations throughout the day:

```
┌─────────────────────────────────────────────────────────────┐
│  Station: Main (meta-schedule)                               │
├──────────────────────────────────────────────────────────────┤
│  Time Range     │ Content                                    │
│  ───────────────┼─────────────────────────────────────────── │
│  06:00 - 09:00  │ → Chill Station                            │
│  09:00 - 12:00  │ → Focus Station                            │
│  12:00 - 17:00  │ → Afternoon Mix Station                    │
│  17:00 - 20:00  │ → Tiny Desk Station                        │
│  20:00 - 22:00  │ → Evening Vibes Station                    │
│  22:00 - 06:00  │ → DnB Station                              │
└──────────────────────────────────────────────────────────────┘

┌─────────────────────┐  ┌─────────────────────┐
│ Station: DnB        │  │ Station: Tiny Desk  │
├─────────────────────┤  ├─────────────────────┤
│ Mode: shuffle       │  │ Mode: queue         │
│ Playlist: DnB       │  │ Playlist:           │
│ (existing music-    │  │ - Tiny Desk YT #1   │
│  minion playlist)   │  │ - Tiny Desk YT #2   │
│                     │  │ - ...               │
└─────────────────────┘  └─────────────────────┘
```

### Schedule Rules

- **Time ranges**: Define start/end times, more natural than hourly blocks
- **Station references**: Main schedule points to other stations
- **Shuffle mode**: Daily-seeded random order (same order all day for determinism)
- **Queue mode**: Plays in order, loops to fill time within the range
- **Recursive calculation**: When Main references DnB, calculates where DnB would be

---

## Data Model

Extends music-minion's existing playlist system with minimal new tables:

```sql
-- Station = playlist + radio metadata
-- Reuses existing `playlists` table, adds radio-specific fields
stations (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,          -- "Main", "DnB", "Chill"
    playlist_id     INTEGER REFERENCES playlists,  -- Links to existing playlist
    mode            TEXT NOT NULL,          -- 'shuffle' | 'queue'
    is_active       BOOLEAN DEFAULT FALSE,  -- Only one active at a time
    created_at      TIMESTAMP,
    updated_at      TIMESTAMP
)

-- Time ranges for meta-stations (like Main)
-- Defines when each station plays during the day
station_schedule (
    id              INTEGER PRIMARY KEY,
    station_id      INTEGER REFERENCES stations,  -- The meta-station (e.g., Main)
    start_time      TEXT NOT NULL,          -- "06:00"
    end_time        TEXT NOT NULL,          -- "09:00"
    target_station  INTEGER REFERENCES stations,  -- Which station plays in this range
    position        INTEGER                 -- Order for overlapping ranges
)

-- Playback history (for v1 - tracking what played)
radio_history (
    id              INTEGER PRIMARY KEY,
    station_id      INTEGER REFERENCES stations,
    track_id        INTEGER REFERENCES tracks,
    source_type     TEXT,                   -- 'local' | 'youtube' | 'spotify' | 'soundcloud'
    source_url      TEXT,                   -- For non-local sources
    started_at      TIMESTAMP,
    ended_at        TIMESTAMP,
    position_ms     INTEGER                 -- Where in track we started (for mid-track joins)
)

-- Current playback state (for resume after restart)
radio_state (
    id              INTEGER PRIMARY KEY,
    active_station  INTEGER REFERENCES stations,
    started_at      TIMESTAMP,
    last_track_id   INTEGER,
    last_position   INTEGER                 -- ms into current track
)

-- Session-level skipped tracks (for fallback handling)
-- Cleared daily with shuffle reseed
radio_skipped (
    id              INTEGER PRIMARY KEY,
    station_id      INTEGER REFERENCES stations,
    track_id        INTEGER,
    source_url      TEXT,
    skipped_at      TIMESTAMP,
    reason          TEXT                    -- 'unavailable' | 'error'
)
```

---

## Deterministic Timeline Calculation

The algorithm that makes "tune in mid-stream" work:

```python
def calculate_now_playing(station_id: int, current_time: datetime) -> NowPlaying:
    """
    Given a station and time, calculate exactly what track
    and position should be playing.
    """
    station = get_station(station_id)

    # 1. If this is a meta-station (has schedule), find the active target station
    schedule = get_schedule_for_time(station_id, current_time)
    if schedule:
        # Recursive: calculate what the target station would be playing
        return calculate_now_playing(schedule.target_station, current_time)

    # 2. Get playlist tracks, excluding any skipped this session
    skipped_ids = get_skipped_tracks(station_id, current_time.date())
    tracks = get_playlist_tracks(station.playlist_id, exclude=skipped_ids)

    # 3. Apply shuffle if needed (deterministic daily seed)
    if station.mode == 'shuffle':
        seed = f"{station_id}-{current_time.date()}"
        tracks = deterministic_shuffle(tracks, seed)

    # 4. Find the time range start for this station
    range_start = find_range_start(station_id, current_time)

    # 5. Calculate position in the playlist
    total_duration = sum(t.duration_ms for t in tracks)
    elapsed_ms = (current_time - range_start).total_seconds() * 1000
    position_in_loop = elapsed_ms % total_duration

    # 6. Walk through to find current track
    accumulated = 0
    for i, track in enumerate(tracks):
        if accumulated + track.duration_ms > position_in_loop:
            return NowPlaying(
                track=track,
                position_ms=position_in_loop - accumulated,
                next_track=tracks[(i + 1) % len(tracks)],
                upcoming=tracks[i+1:i+6]  # Next 5 tracks for queue display
            )
        accumulated += track.duration_ms


def get_next_track_with_fallback(station_id: int, current_time: datetime) -> Track:
    """
    Get next track, handling unavailable sources gracefully.
    """
    now_playing = calculate_now_playing(station_id, current_time)

    if not is_available(now_playing.track):
        # Mark as skipped, recalculate
        mark_skipped(station_id, now_playing.track, reason='unavailable')
        return get_next_track_with_fallback(station_id, current_time)

    return now_playing.track
```

### Edge Cases

- **Time range spans midnight**: Handled by checking if current time is within range accounting for wrap
- **Content shorter than range**: Loops via modulo
- **Server restart**: Recalculates from scratch - no state needed for timeline
- **Schedule change**: Recalculates immediately with new content
- **Circular station references**: Depth check prevents Main → DnB → Main loops
- **Unavailable source**: Skip and recalculate, shuffle order preserved minus skipped tracks
- **All tracks unavailable**: Fall back to a designated "emergency" local-only station

---

## Audio Pipeline

### Liquidsoap Configuration

```liquidsoap
# Dynamic source - scheduler tells us what to play
queue = request.dynamic(
  fun() -> get_next_track()  # HTTP call to music-minion scheduler
)

# Add crossfading between tracks
radio = crossfade(queue)

# Normalize volume
radio = normalize(radio)

# Output to Icecast
output.icecast(
  %opus(bitrate=128),
  host="localhost", port=8000,
  password="hackme", mount="/stream",
  radio
)
```

### Source Handling

| Source | How Liquidsoap plays it |
|--------|------------------------|
| Local Opus file | Direct file path |
| YouTube | `yt-dlp -o - URL` piped as stream |
| Spotify | librespot outputs to FIFO, Liquidsoap reads it |
| SoundCloud | Direct HTTPS stream URL |

### Mid-Track Seeking

When calculating now-playing, if we're 3:33 into a track, use ffmpeg to seek before feeding to Liquidsoap. This only happens on initial tune-in or schedule change.

---

## Web UI

### URL Structure

```
mm.kevinandrews.info/
├── /           → Web UI (now playing, schedule editor, audio player)
├── /stream     → Raw Icecast audio stream (for casting)
└── /video      → YouTube video player (standalone)
```

### Main UI (`/`)

```
┌─────────────────────────────────────────────────────────────────┐
│  Personal Radio                                       [Main ▼]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │  ▶ NOW PLAYING                                             │ │
│  │  "Tiny Desk Concert - Anderson .Paak"                      │ │
│  │   ━━━━━━━━━━━━━━━━●━━━━━━━━━━━━                            │ │
│  │  ▷ 12:34 / 18:22                               [🔊 Mute]   │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌─ UP NEXT ────────────────────────────────────────────────┐   │
│  │  1. Khruangbin - Time (You and I)              4:32       │   │
│  │  2. Vulfpeck - Dean Town                       2:58       │   │
│  │  3. Hiatus Kaiyote - Nakamarra                 5:14       │   │
│  │  4. Tiny Desk - Mac Miller                    18:45       │   │
│  │  5. Thundercat - Them Changes                  3:23       │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─ HISTORY ────────────────────────────────────────────────┐   │
│  │  2:15pm  Tiny Desk - Anderson .Paak           (playing)   │   │
│  │  1:47pm  Khruangbin - Maria También            4:28       │   │
│  │  1:42pm  Tom Misch - South of the River        5:02       │   │
│  │  1:38pm  FKJ - Vibin' Out                      3:56       │   │
│  │                                            [View All →]   │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─ SCHEDULE ───────────────────────────────────────────────┐   │
│  │  12:00-17:00  ●━━━ → Tiny Desk              [Edit]        │   │
│  │  17:00-20:00  ○─── → Evening Chill          [Edit]        │   │
│  │  20:00-22:00  ○─── → DnB                    [Edit]        │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─ STATIONS ───────────────────────────────────────────────┐   │
│  │  Main (active)  │  DnB  │  Chill  │  Tiny Desk  │  [+]    │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### History Page (`/history`)

Full playback history with filtering:
- Filter by station, date range, source type
- Search by track name/artist
- Stats: most played tracks, listening time per station
- Export options for analysis

### Video Page (`/video`)

Standalone YouTube player that:
- Calculates what YouTube video should be playing (same deterministic logic)
- Embeds YouTube player at calculated position with its own audio
- Preloads next video ~30 seconds before transition for smooth advancement
- Shows "Audio Only" card when non-YouTube content is playing

```
┌─────────────────────────────────────────────────────────────┐
│  mm.kevinandrews.info/video                                 │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐  │
│  │                                                       │  │
│  │              YouTube Embed                            │  │
│  │         (with its own audio playing)                  │  │
│  │                                                       │  │
│  └───────────────────────────────────────────────────────┘  │
│  Up next: Evening Chill playlist (audio only)              │
│                                                             │
│  [Preloading next YouTube video in background]             │
└─────────────────────────────────────────────────────────────┘
```

### API Endpoints

```
GET  /api/radio/now-playing          # Current track, position, upcoming queue
GET  /api/radio/stations             # List all stations
POST /api/radio/stations/{id}/activate   # Switch active station
GET  /api/radio/stations/{id}/schedule   # Get schedule for a station
PUT  /api/radio/schedule/{id}        # Update a schedule time range
POST /api/radio/schedule             # Add a schedule time range
DELETE /api/radio/schedule/{id}      # Remove a schedule time range

GET  /api/radio/history              # Playback history (paginated, filterable)
GET  /api/radio/history/stats        # Listening stats (most played, time per station)

WS   /api/radio/live                 # WebSocket for real-time updates
```

---

## Deployment

### Target: Raspberry Pi (128GB)

```
┌─────────────────────────────────────────────────────────────────┐
│  Raspberry Pi 4/5                                                │
│  mm.kevinandrews.info                                           │
├─────────────────────────────────────────────────────────────────┤
│  Docker Compose:                                                 │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐                   │
│  │ Liquidsoap│→ │  Icecast  │→ │  Caddy    │→ HTTPS            │
│  └───────────┘  └───────────┘  └───────────┘                   │
│        ↑                             ↑                          │
│  ┌───────────┐                 ┌───────────┐                   │
│  │  FastAPI  │                 │   React   │                   │
│  │  Backend  │                 │  Frontend │                   │
│  └───────────┘                 └───────────┘                   │
│                                                                  │
│  Volumes:                                                        │
│  - /music (Opus files, synced via Syncthing)                    │
│  - /data (SQLite database)                                      │
└─────────────────────────────────────────────────────────────────┘
```

### Storage Estimate

```
128 GB total
  - 8 GB   OS + Docker + packages
  - 18 GB  Music library (33GB MP3 → ~18GB Opus 128kbps)
  - 2 GB   Database, logs, cache
─────────────────────────
 ~100 GB   Free for growth
```

### Music Library Sync

1. Keep original MP3s on desktop as source of truth
2. Convert to Opus 128kbps for radio library
3. Sync radio library to Pi via Syncthing
4. music-minion CLI on desktop stays separate (not connected to radio)

### Docker Compose Structure

```yaml
version: '3.8'
services:
  icecast:
    image: infiniteproject/icecast
    ports:
      - "8000:8000"
    volumes:
      - ./icecast.xml:/etc/icecast.xml

  liquidsoap:
    build: ./liquidsoap
    depends_on:
      - icecast
    volumes:
      - ./music:/music:ro
      - ./radio.liq:/etc/liquidsoap/radio.liq

  backend:
    build: ./backend
    depends_on:
      - liquidsoap
    volumes:
      - ./data:/data
    environment:
      - DATABASE_PATH=/data/radio.db

  frontend:
    build: ./frontend
    depends_on:
      - backend

  caddy:
    image: caddy:2
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
```

---

## Home Assistant Integration

For wake-up alarm and casting to Google speakers:

```yaml
# automation.yaml
- alias: "Morning Radio Wake Up"
  trigger:
    - platform: time
      at: "07:00:00"
  action:
    - service: media_player.play_media
      target:
        entity_id: media_player.bedroom_speaker
      data:
        media_content_id: "http://mm.kevinandrews.info/stream"
        media_content_type: "audio/ogg"
    - service: media_player.volume_set
      target:
        entity_id: media_player.bedroom_speaker
      data:
        volume_level: 0.1
    # Ramp volume over 10 minutes
    - repeat:
        count: 10
        sequence:
          - delay: "00:01:00"
          - service: media_player.volume_up
            target:
              entity_id: media_player.bedroom_speaker
```

---

## Integration with music-minion

### File Structure

```
src/music_minion/
├── domain/
│   ├── library/          # existing
│   ├── playback/         # existing
│   └── radio/            # NEW MODULE
│       ├── stations.py       # Station CRUD
│       ├── schedule.py       # Block management
│       ├── timeline.py       # Deterministic position calculation
│       ├── scheduler.py      # Main loop - feeds Liquidsoap
│       └── sources.py        # Source adapters
│
├── commands/
│   └── radio.py          # NEW - CLI commands
│
web/
├── backend/routes/
│   └── radio.py          # NEW - FastAPI endpoints
│
├── frontend/src/pages/
│   ├── Radio.tsx         # NEW - main radio UI
│   └── Video.tsx         # NEW - /video page
```

### Reused Components

| Existing | Used for |
|----------|----------|
| `tracks` table | Track metadata, durations |
| `playlists` table | Playlist references in blocks |
| SoundCloud provider | Stream URL resolution |
| Spotify auth | librespot credentials |
| FastAPI backend | New radio endpoints |
| React frontend | New radio pages |

### New Dependencies

- **Liquidsoap** - Audio engine
- **Icecast** - Streaming server
- **librespot** - Spotify playback (optional)
- **yt-dlp** - YouTube audio (already installed)
- **ffmpeg** - Seeking, transcoding

---

## Implementation Phases

### Phase 1: Core Radio
- [ ] Data model (stations, schedule, history, skipped)
- [ ] Deterministic timeline calculation with time ranges
- [ ] Fallback/skip logic for unavailable sources
- [ ] Liquidsoap integration (local files only)
- [ ] Icecast streaming
- [ ] Basic web UI (now playing, station switching)

### Phase 2: Schedule & History
- [ ] Time range schedule editor UI
- [ ] Station references in schedules
- [ ] Shuffle vs queue modes
- [ ] Playback history tracking
- [ ] History + upcoming queue display in UI
- [ ] History page with filtering/stats

### Phase 3: Multi-Source
- [ ] YouTube via yt-dlp
- [ ] SoundCloud stream URLs
- [ ] Spotify via librespot
- [ ] Source-specific seeking
- [ ] Source availability checking

### Phase 4: Video Page
- [ ] /video route with YouTube embed
- [ ] Sync to calculated position
- [ ] Preloading next video
- [ ] Audio-only card fallback

### Phase 5: Deployment
- [ ] Docker Compose setup
- [ ] Opus conversion script
- [ ] Syncthing configuration
- [ ] Caddy HTTPS reverse proxy
- [ ] Home Assistant automation examples

---

## Open Questions

1. **Crossfade duration**: 3-5 seconds? Configurable per station?
2. **Schedule timezone**: Server local time? User configurable?
3. **Mobile app**: PWA sufficient, or native app later?

---

## Future Ideas (Post-V1)

These were discussed during design but deferred for later versions:

### Quick Add from Anywhere
- Browser extension: "Add to Radio" button on YouTube/Spotify/SoundCloud
- Mobile share target: Share URL → radio adds it to station
- Telegram/Discord bot: Send link to queue or schedule
- iOS Shortcut / Android intent for quick-add

### AI DJ Personality
- TTS clips between tracks with contextual commentary
- "That was Miles Davis. Coming up, some Khruangbin to ease into the afternoon..."
- Configurable personality per station
- Triggered occasionally, not every track

### Time-Shifted Listening (Radio DVR)
- "What was playing at 8am?"
- Rewind the virtual timeline
- Star something from earlier → adds to library
- Uses deterministic timeline to calculate backwards

### Reactive Scheduling
- Weather API integration: Rainy day → mellow music
- Calendar awareness: Meeting soon → shorter tracks
- Sunset-based time ranges instead of fixed times
- Manual mood buttons to shift programming

### Collaborative Stations
- Friends can tune in and see what's playing
- Optional request/queue system
- Shared activity feed

### Visual Radio Mode
- Visualizer synced to audio when no video content
- Album art slideshow
- Generated visuals based on track mood
- Clock/weather overlay

### Smart Transitions
- BPM-aware shuffle ordering
- Key-compatible sequencing
- Dynamic crossfade based on track endings
- Energy ramping over time ranges

### Podcast Support
- RSS feed integration
- "Play morning news at 7am"
- Track which episodes have played
- Note: Less "radio" since podcasts are sequential

---

## Resources

- [Liquidsoap Documentation](https://www.liquidsoap.info/doc-dev/)
- [Icecast Documentation](https://icecast.org/docs/)
- [librespot](https://github.com/librespot-org/librespot)
- [Opus Codec](https://opus-codec.org/)
