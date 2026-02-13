# Liquidsoap Scheduler Integration

## Files to Modify/Create
- `src/music_minion/domain/radio/scheduler.py` (new - HTTP endpoint for Liquidsoap)
- `src/music_minion/domain/radio/sources.py` (new - source URL resolution)
- `deployment/liquidsoap/radio.liq` (new - Liquidsoap config)
- `deployment/liquidsoap/Dockerfile` (new)

## Implementation Details

Create the scheduler endpoint that Liquidsoap polls for next track, and configure Liquidsoap for streaming.

### Scheduler HTTP Endpoint (`scheduler.py`)

```python
from datetime import datetime
from pathlib import Path
import subprocess
import tempfile
from music_minion.domain.radio.builder import get_now_playing
from music_minion.domain.radio.sources import resolve_source_url
from music_minion.core.database import get_db_connection


def get_next_track_for_liquidsoap(station_id: int) -> dict:
    """
    Return next track for Liquidsoap to play.

    Returns:
        {
            "uri": "/music/file.opus" or "/tmp/seeked_12345.opus",
            "seek_ms": 0,  # 0 for normal playback, >0 if pre-seeked
            "duration_ms": 285000,
            "track_id": 1234
        }
    """
    current_time = datetime.now()
    scheduled = get_now_playing(station_id, current_time)

    if not scheduled:
        # Fallback to emergency track
        return get_emergency_track()

    # Calculate if we need to seek (tune-in mid-track)
    elapsed_ms = (current_time - scheduled.scheduled_start).total_seconds() * 1000
    seek_ms = int(elapsed_ms) if elapsed_ms > 0 else 0

    # Resolve source URL to playable path
    uri = resolve_source_url(scheduled.source_url, scheduled.source_type)

    # If seeking needed, pre-process with ffmpeg
    if seek_ms > 1000:  # Only seek if >1 second in
        uri = _create_seeked_file(uri, seek_ms)
        seek_ms = 0  # File already seeked

    # Log playback start
    _log_playback_start(station_id, scheduled.track_id, seek_ms)

    return {
        "uri": uri,
        "seek_ms": seek_ms,
        "duration_ms": scheduled.track_id.duration_ms,  # TODO: fetch from tracks table
        "track_id": scheduled.track_id
    }


def _create_seeked_file(source_path: str, seek_ms: int) -> str:
    """Create a temp file seeked to position using ffmpeg."""
    seek_seconds = seek_ms / 1000
    temp_file = tempfile.NamedTemporaryFile(
        suffix=Path(source_path).suffix,
        delete=False
    )

    subprocess.run([
        'ffmpeg', '-y',
        '-ss', str(seek_seconds),
        '-i', source_path,
        '-c', 'copy',  # Stream copy (no re-encode)
        temp_file.name
    ], check=True, capture_output=True)

    return temp_file.name


def _log_playback_start(station_id: int, track_id: int, position_ms: int):
    """Log track playback to radio_history."""
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO radio_history
            (station_id, track_id, started_at, position_ms)
            VALUES (%s, %s, NOW(), %s)
        """, (station_id, track_id, position_ms))
        conn.commit()


def get_emergency_track() -> dict:
    """Fallback track when schedule is empty or all tracks unavailable."""
    # Return a known-good local file
    return {
        "uri": "/path/to/emergency/silence.opus",
        "seek_ms": 0,
        "duration_ms": 60000,
        "track_id": -1
    }
```

### Source Resolution (`sources.py`)

```python
from pathlib import Path


def resolve_source_url(source_url: str, source_type: str) -> str:
    """
    Resolve permanent source URL to playable path.

    For local: Returns file path directly
    For remote: Returns protocol handler for Liquidsoap
    """
    if source_type == 'local':
        return source_url  # Already a file path

    elif source_type == 'youtube':
        # Liquidsoap will use youtube-dl protocol
        # Return format: protocol://path
        return f"youtube-dl:{source_url}"

    elif source_type == 'soundcloud':
        # Also use youtube-dl (it supports SoundCloud)
        return f"youtube-dl:{source_url}"

    elif source_type == 'spotify':
        # TODO: Implement librespot FIFO integration
        raise NotImplementedError("Spotify support in Phase 3")

    else:
        raise ValueError(f"Unknown source type: {source_type}")
```

### Liquidsoap Configuration (`deployment/liquidsoap/radio.liq`)

```liquidsoap
#!/usr/bin/liquidsoap

# Settings
set("log.file.path", "/var/log/liquidsoap/radio.log")
set("log.level", 3)

# HTTP endpoint for next track
def get_next_track() =
  # Call music-minion scheduler endpoint
  result = http.get("http://backend:8000/api/radio/next-track")

  # Parse JSON response
  data = json.parse(result)
  uri = data["uri"]

  # Return URI for Liquidsoap to play
  [request.create(uri)]
end

# Dynamic queue fed by scheduler
queue = request.dynamic(get_next_track)

# Add crossfading between tracks
radio = crossfade(duration=3.0, queue)

# Normalize volume
radio = normalize(radio)

# Output to Icecast
output.icecast(
  %opus(bitrate=128, samplerate=48000),
  host="icecast",
  port=8000,
  password="hackme",
  mount="/stream",
  name="Personal Radio",
  description="24/7 personal radio station",
  radio
)

# Also output to local file for debugging
output.file(
  %opus(bitrate=128),
  "/tmp/radio_debug.opus",
  fallible=true,
  radio
)
```

### Liquidsoap Dockerfile

```dockerfile
FROM savonet/liquidsoap:v2.2.4

# Install dependencies for youtube-dl support
RUN apt-get update && apt-get install -y \
    yt-dlp \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy radio script
COPY radio.liq /etc/liquidsoap/radio.liq

# Create log directory
RUN mkdir -p /var/log/liquidsoap

CMD ["liquidsoap", "/etc/liquidsoap/radio.liq"]
```

## Acceptance Criteria

- [ ] `/api/radio/next-track` endpoint returns JSON with URI, seek_ms, duration_ms
- [ ] ffmpeg seeking creates temp files correctly when tune-in mid-track
- [ ] Source resolution handles local, YouTube, SoundCloud URLs
- [ ] Liquidsoap successfully polls endpoint and plays returned URIs
- [ ] Crossfade works between tracks (3-second overlap)
- [ ] Icecast stream accessible at `http://localhost:8000/stream`
- [ ] Playback logged to `radio_history` table

## Dependencies

- Requires: **03-station-crud-and-schedule-builder.md** (schedule builder must exist)

## Testing

```bash
# Start Icecast and Liquidsoap via Docker Compose
docker compose up icecast liquidsoap

# Test scheduler endpoint
curl http://localhost:8000/api/radio/next-track
# Expected: {"uri": "/music/...", "seek_ms": 0, ...}

# Listen to stream
mpv http://localhost:8000/stream

# Check logs
docker compose logs liquidsoap
```

## Notes

- **youtube-dl protocol**: Liquidsoap has built-in support via `protocol.external`
- **Temp file cleanup**: Implement periodic cleanup of `/tmp/seeked_*.opus` files
- **Error handling**: If scheduler endpoint fails, Liquidsoap should retry with exponential backoff
