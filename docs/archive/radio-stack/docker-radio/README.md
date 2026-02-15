# Personal Radio - Docker Setup

Local development environment for the personal radio streaming stack.

## Components

- **Icecast**: HTTP streaming server (port 8000)
- **Liquidsoap**: Audio engine with crossfading and normalization (telnet port 1234)

## Quick Start

```bash
# Start the stack
docker compose up -d

# View logs
docker compose logs -f

# Stop the stack
docker compose down
```

## Testing

### Listen to the stream

```bash
# Using ffplay
ffplay http://localhost:8000/stream

# Using VLC
vlc http://localhost:8000/stream

# Using mpv
mpv http://localhost:8000/stream
```

### Icecast web interface

Open http://localhost:8000 in a browser to see listener stats.

Admin interface: http://localhost:8000/admin (user: admin, password: admin123)

### Telnet control

```bash
telnet localhost 1234

# Available commands:
help                    # List all commands
request.queue           # Show current queue
radio_queue.uri         # Show current track URI
radio_queue.skip        # Skip current track
exit                    # Close connection
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Python         │────>│   Liquidsoap    │────>│    Icecast      │
│  Scheduler      │     │   (audio)       │     │   (streaming)   │
│  :8001          │     │   :1234 telnet  │     │   :8000 http    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
     │                         │                       │
     │  GET /api/radio/        │                       │
     │      next-track         │                       │
     └─────────────────────────┘                       │
                                                       v
                                              ┌─────────────────┐
                                              │    Listeners    │
                                              │   (browsers,    │
                                              │    speakers)    │
                                              └─────────────────┘
```

## Configuration

### Environment Variables (Liquidsoap)

| Variable | Default | Description |
|----------|---------|-------------|
| `ICECAST_HOST` | `icecast` | Icecast server hostname |
| `ICECAST_PORT` | `8000` | Icecast server port |
| `ICECAST_PASSWORD` | `hackme` | Source password |
| `ICECAST_MOUNT` | `/stream` | Mount point path |
| `SCHEDULER_URL` | `http://host.docker.internal:8001/api/radio/next-track` | Python scheduler endpoint |

### Passwords (Development Only)

- Source password: `hackme`
- Admin password: `admin123`

**Change these for production deployment.**

## Music Library

The compose file mounts `../../music` as the music library. Adjust this path in `docker-compose.yml` if your music is elsewhere.

Liquidsoap expects the scheduler to return absolute paths like `/music/Artist/Album/Track.opus`.

## Scheduler API Contract

The Python scheduler must expose:

```
GET /api/radio/next-track

Response (200):
/music/path/to/track.opus

Response (404/500):
Liquidsoap will retry after 5 seconds
```

## Troubleshooting

### No audio playing

1. Check if scheduler is running: `curl http://localhost:8001/api/radio/next-track`
2. Check Liquidsoap logs: `docker compose logs liquidsoap`
3. Verify music files exist in the mounted volume

### Connection refused to Icecast

1. Wait for Icecast healthcheck to pass
2. Check Icecast logs: `docker compose logs icecast`

### Liquidsoap crashes on startup

1. Syntax error in `radio.liq` - check logs for line numbers
2. Missing environment variables
3. Icecast not ready - the healthcheck should prevent this

## Audio Pipeline

1. **Source**: Dynamic requests from Python scheduler
2. **ReplayGain**: Volume normalization based on track metadata
3. **Normalize**: Target -14 LUFS for consistent loudness
4. **Crossfade**: 3-second smart crossfade between tracks
5. **Output**: Opus 128kbps to Icecast
