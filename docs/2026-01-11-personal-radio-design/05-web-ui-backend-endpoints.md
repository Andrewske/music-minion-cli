# Web UI Backend Endpoints

## Files to Modify/Create
- `web/backend/routes/radio.py` (new - FastAPI routes)
- `web/backend/main.py` (modify - register radio routes)

## Implementation Details

Create FastAPI endpoints for radio station management, schedule editing, and real-time updates.

### Radio Routes (`web/backend/routes/radio.py`)

```python
from fastapi import APIRouter, HTTPException, WebSocket
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel

from music_minion.domain.radio import stations, builder
from music_minion.domain.radio.scheduler import get_next_track_for_liquidsoap
from music_minion.core.database import get_db_connection


router = APIRouter(prefix="/api/radio", tags=["radio"])


# ===== Models =====

class StationCreate(BaseModel):
    name: str
    playlist_id: int
    mode: str  # 'shuffle' | 'queue'


class TimeRangeCreate(BaseModel):
    start_time: str  # "06:00"
    end_time: str    # "09:00"
    target_station: int
    position: int


class NowPlayingResponse(BaseModel):
    track_id: int
    title: str
    artist: str
    position_ms: int
    duration_ms: int
    upcoming: list[dict]  # Next 5 tracks


# ===== Stations =====

@router.get("/stations")
async def list_stations():
    """List all radio stations."""
    with get_db_connection() as conn:
        result = conn.execute("SELECT * FROM stations ORDER BY name")
        return [dict(row) for row in result.fetchall()]


@router.post("/stations")
async def create_station(data: StationCreate):
    """Create a new radio station."""
    station = stations.create_station(data.name, data.playlist_id, data.mode)
    return station


@router.post("/stations/{station_id}/activate")
async def activate_station(station_id: int):
    """Set a station as the active streaming station."""
    stations.set_active_station(station_id)
    # Rebuild today's schedule for new active station
    builder.build_daily_schedule(station_id, date.today())
    return {"status": "activated", "station_id": station_id}


# ===== Schedule =====

@router.get("/stations/{station_id}/schedule")
async def get_station_schedule(station_id: int):
    """Get time ranges for a meta-station."""
    ranges = stations.get_time_ranges(station_id)
    return [
        {
            "id": r.id,
            "start_time": r.start_time,
            "end_time": r.end_time,
            "target_station": r.target_station,
            "position": r.position
        }
        for r in ranges
    ]


@router.post("/schedule")
async def add_schedule_range(data: TimeRangeCreate):
    """Add a time range to a meta-station's schedule."""
    # TODO: Add debounce mechanism (queue rebuild, execute after 2s of no edits)
    time_range = stations.add_time_range(
        station_id=data.station_id,
        start_time=data.start_time,
        end_time=data.end_time,
        target_station=data.target_station,
        position=data.position
    )
    return time_range


@router.put("/schedule/{range_id}")
async def update_schedule_range(range_id: int, data: TimeRangeCreate):
    """Update an existing time range."""
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE station_schedule
            SET start_time = %s, end_time = %s,
                target_station = %s, position = %s
            WHERE id = %s
        """, (data.start_time, data.end_time, data.target_station,
              data.position, range_id))
        conn.commit()
    return {"status": "updated", "range_id": range_id}


@router.delete("/schedule/{range_id}")
async def delete_schedule_range(range_id: int):
    """Remove a time range from schedule."""
    with get_db_connection() as conn:
        conn.execute("DELETE FROM station_schedule WHERE id = %s", (range_id,))
        conn.commit()
    return {"status": "deleted"}


# ===== Now Playing =====

@router.get("/now-playing")
async def get_now_playing():
    """Get currently playing track with upcoming queue."""
    # Get active station
    with get_db_connection() as conn:
        result = conn.execute("SELECT id FROM stations WHERE is_active = TRUE LIMIT 1")
        row = result.fetchone()

        if not row:
            raise HTTPException(404, "No active station")

        station_id = row[0]

    # Get current scheduled track
    current_time = datetime.now()
    scheduled = builder.get_now_playing(station_id, current_time)

    if not scheduled:
        raise HTTPException(404, "Nothing scheduled right now")

    # Get track details
    with get_db_connection() as conn:
        result = conn.execute(
            "SELECT * FROM tracks WHERE id = %s",
            (scheduled.track_id,)
        )
        track = dict(result.fetchone())

        # Get upcoming tracks
        result = conn.execute("""
            SELECT t.* FROM daily_schedule ds
            JOIN tracks t ON ds.track_id = t.id
            WHERE ds.station_id = %s AND ds.date = %s
              AND ds.position > %s
            ORDER BY ds.position
            LIMIT 5
        """, (station_id, current_time.date(), scheduled.position))
        upcoming = [dict(row) for row in result.fetchall()]

    # Calculate position in current track
    elapsed_ms = int((current_time - scheduled.scheduled_start).total_seconds() * 1000)

    return {
        "track_id": track["id"],
        "title": track["title"],
        "artist": track["artist"],
        "position_ms": elapsed_ms,
        "duration_ms": track["duration_ms"],
        "upcoming": upcoming
    }


# ===== History =====

@router.get("/history")
async def get_playback_history(
    station_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0
):
    """Get paginated playback history."""
    with get_db_connection() as conn:
        query = """
            SELECT rh.*, t.title, t.artist, s.name as station_name
            FROM radio_history rh
            JOIN tracks t ON rh.track_id = t.id
            JOIN stations s ON rh.station_id = s.id
        """
        params = []

        if station_id:
            query += " WHERE rh.station_id = %s"
            params.append(station_id)

        query += " ORDER BY rh.started_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        result = conn.execute(query, tuple(params))
        return [dict(row) for row in result.fetchall()]


@router.get("/history/stats")
async def get_history_stats():
    """Get listening statistics."""
    with get_db_connection() as conn:
        # Most played tracks
        result = conn.execute("""
            SELECT t.title, t.artist, COUNT(*) as play_count
            FROM radio_history rh
            JOIN tracks t ON rh.track_id = t.id
            GROUP BY t.id, t.title, t.artist
            ORDER BY play_count DESC
            LIMIT 10
        """)
        most_played = [dict(row) for row in result.fetchall()]

        # Listening time per station
        result = conn.execute("""
            SELECT s.name, COUNT(*) as track_count,
                   SUM(EXTRACT(EPOCH FROM (rh.ended_at - rh.started_at))) as total_seconds
            FROM radio_history rh
            JOIN stations s ON rh.station_id = s.id
            WHERE rh.ended_at IS NOT NULL
            GROUP BY s.id, s.name
            ORDER BY total_seconds DESC
        """)
        station_stats = [dict(row) for row in result.fetchall()]

    return {
        "most_played": most_played,
        "station_stats": station_stats
    }


# ===== Liquidsoap Endpoint =====

@router.get("/next-track")
async def next_track():
    """Endpoint for Liquidsoap to poll for next track."""
    # Get active station
    with get_db_connection() as conn:
        result = conn.execute("SELECT id FROM stations WHERE is_active = TRUE LIMIT 1")
        row = result.fetchone()

        if not row:
            # No active station - return emergency track
            from music_minion.domain.radio.scheduler import get_emergency_track
            return get_emergency_track()

        station_id = row[0]

    # Get next track with seeking if needed
    return get_next_track_for_liquidsoap(station_id)


# ===== WebSocket for Live Updates =====

@router.websocket("/live")
async def websocket_live(websocket: WebSocket):
    """WebSocket for real-time now-playing updates."""
    await websocket.accept()

    try:
        while True:
            # Poll current track every 5 seconds
            await asyncio.sleep(5)
            now_playing = await get_now_playing()
            await websocket.send_json(now_playing)
    except Exception as e:
        await websocket.close()
```

### Register Routes (`web/backend/main.py`)

```python
# Add to existing main.py
from web.backend.routes import radio

app.include_router(radio.router)
```

## Acceptance Criteria

- [ ] All endpoints return proper JSON responses
- [ ] Station CRUD operations work (create, list, activate)
- [ ] Schedule time ranges can be added/updated/deleted
- [ ] `/now-playing` returns current track with position and upcoming queue
- [ ] `/history` returns paginated playback history
- [ ] `/history/stats` returns most played tracks and station statistics
- [ ] `/next-track` endpoint works for Liquidsoap polling
- [ ] WebSocket `/live` sends real-time updates every 5 seconds
- [ ] Error handling returns appropriate HTTP status codes

## Dependencies

- Requires: **04-liquidsoap-scheduler-integration.md** (scheduler functions must exist)

## Testing

```python
from fastapi.testclient import TestClient

def test_create_station(client: TestClient):
    response = client.post("/api/radio/stations", json={
        "name": "Test Station",
        "playlist_id": 1,
        "mode": "shuffle"
    })
    assert response.status_code == 200
    assert response.json()["name"] == "Test Station"


def test_now_playing(client: TestClient):
    # Activate station and build schedule
    client.post("/api/radio/stations/1/activate")

    response = client.get("/api/radio/now-playing")
    assert response.status_code == 200
    data = response.json()
    assert "track_id" in data
    assert "upcoming" in data
    assert len(data["upcoming"]) <= 5
```
