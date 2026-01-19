# Station CRUD and Daily Schedule Builder

## Files to Modify/Create
- `src/music_minion/domain/radio/stations.py` (new)
- `src/music_minion/domain/radio/schedule.py` (new)
- `src/music_minion/domain/radio/builder.py` (new - daily schedule builder)

## Implementation Details

Implement station management and the nightly schedule builder that pre-computes the day's playlist with boundary-aware track selection.

### Station CRUD (`stations.py`)

```python
from datetime import datetime
from typing import Optional
from music_minion.core.database import get_db_connection
from music_minion.domain.radio.models import Station, StationSchedule


def create_station(name: str, playlist_id: int, mode: str) -> Station:
    """Create a new radio station."""
    with get_db_connection() as conn:
        result = conn.execute("""
            INSERT INTO stations (name, playlist_id, mode, is_active)
            VALUES (%s, %s, %s, FALSE)
            RETURNING id, name, playlist_id, mode, is_active, created_at, updated_at
        """, (name, playlist_id, mode))
        conn.commit()
        row = result.fetchone()
        return Station(**dict(row))


def get_station(station_id: int) -> Optional[Station]:
    """Get station by ID."""
    with get_db_connection() as conn:
        result = conn.execute(
            "SELECT * FROM stations WHERE id = %s",
            (station_id,)
        )
        row = result.fetchone()
        return Station(**dict(row)) if row else None


def set_active_station(station_id: int) -> None:
    """Set a station as active (deactivates all others)."""
    with get_db_connection() as conn:
        # Deactivate all
        conn.execute("UPDATE stations SET is_active = FALSE")
        # Activate target
        conn.execute(
            "UPDATE stations SET is_active = TRUE WHERE id = %s",
            (station_id,)
        )
        conn.commit()


def add_time_range(
    station_id: int,
    start_time: str,
    end_time: str,
    target_station: int,
    position: int
) -> StationSchedule:
    """Add a time range to a meta-station's schedule."""
    with get_db_connection() as conn:
        result = conn.execute("""
            INSERT INTO station_schedule
            (station_id, start_time, end_time, target_station, position)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
        """, (station_id, start_time, end_time, target_station, position))
        conn.commit()
        return StationSchedule(**dict(result.fetchone()))


def get_time_ranges(station_id: int) -> list[StationSchedule]:
    """Get all time ranges for a station, ordered by position."""
    with get_db_connection() as conn:
        result = conn.execute("""
            SELECT * FROM station_schedule
            WHERE station_id = %s
            ORDER BY position
        """, (station_id,))
        return [StationSchedule(**dict(row)) for row in result.fetchall()]
```

### Daily Schedule Builder (`builder.py`)

```python
from datetime import date, datetime, timedelta
from typing import Optional
from music_minion.domain.radio.models import ScheduledTrack, StationSchedule
from music_minion.domain.radio.stations import get_station, get_time_ranges
from music_minion.domain.playlists import get_playlist_tracks
from music_minion.core.database import get_db_connection
import random


def build_daily_schedule(station_id: int, target_date: date) -> list[ScheduledTrack]:
    """
    Build boundary-aware schedule for the day.

    Walks through each time range, shuffles content, and swaps in shorter
    tracks when approaching boundaries to avoid >5 minute overshoot.
    """
    schedule = []
    position = 0
    time_ranges = get_time_ranges(station_id)

    for time_range in time_ranges:
        target = get_station(time_range.target_station)
        tracks = get_playlist_tracks(target.playlist_id)

        # Apply shuffle with daily seed for determinism
        if target.mode == 'shuffle':
            seed = f"{target.id}-{target_date}"
            random.Random(seed).shuffle(tracks)

        remaining = list(tracks)
        current_time = _parse_time_today(time_range.start_time, target_date)
        range_end = _parse_time_today(time_range.end_time, target_date)

        # Handle midnight wrap (e.g., 22:00 - 06:00)
        if range_end < current_time:
            range_end += timedelta(days=1)

        while current_time < range_end and remaining:
            track = remaining.pop(0)
            track_duration = timedelta(milliseconds=track.duration_ms)
            end_time = current_time + track_duration
            overshoot = (end_time - range_end).total_seconds()

            # Boundary-aware track swapping
            if overshoot > 300:  # >5 min overshoot
                max_duration_sec = (range_end - current_time).total_seconds() + 300
                better = next(
                    (t for t in remaining if t.duration_ms / 1000 < max_duration_sec),
                    None
                )
                if better:
                    remaining.remove(better)
                    remaining.insert(0, track)  # Put long track back
                    track = better
                    track_duration = timedelta(milliseconds=track.duration_ms)
                    end_time = current_time + track_duration

            # Add load gap padding for remote sources
            if track.source_type in ('youtube', 'soundcloud'):
                end_time += timedelta(seconds=3)

            schedule.append(ScheduledTrack(
                id=None,
                station_id=station_id,
                date=target_date,
                track_id=track.id,
                source_type=track.source_type,
                source_url=track.source_url,
                scheduled_start=current_time,
                scheduled_end=end_time,
                position=position,
                time_range_id=time_range.id
            ))
            position += 1
            current_time = end_time

    # Store in database
    save_daily_schedule(station_id, target_date, schedule)
    return schedule


def save_daily_schedule(station_id: int, target_date: date, schedule: list[ScheduledTrack]):
    """Save pre-computed schedule to database, replacing existing."""
    with get_db_connection() as conn:
        # Clear existing schedule for this date
        conn.execute(
            "DELETE FROM daily_schedule WHERE station_id = %s AND date = %s",
            (station_id, target_date)
        )

        # Batch insert new schedule
        if schedule:
            conn.executemany("""
                INSERT INTO daily_schedule
                (station_id, date, track_id, source_type, source_url,
                 scheduled_start, scheduled_end, position, time_range_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, [
                (s.station_id, s.date, s.track_id, s.source_type, s.source_url,
                 s.scheduled_start, s.scheduled_end, s.position, s.time_range_id)
                for s in schedule
            ])

        conn.commit()


def get_now_playing(station_id: int, current_time: datetime) -> Optional[ScheduledTrack]:
    """Look up what should be playing from pre-computed schedule."""
    with get_db_connection() as conn:
        result = conn.execute("""
            SELECT * FROM daily_schedule
            WHERE station_id = %s AND date = %s
              AND scheduled_start <= %s AND scheduled_end > %s
            ORDER BY position
            LIMIT 1
        """, (station_id, current_time.date(), current_time, current_time))

        row = result.fetchone()
        return ScheduledTrack(**dict(row)) if row else None


def _parse_time_today(time_str: str, target_date: date) -> datetime:
    """Parse '06:00' format to datetime on target date."""
    hour, minute = map(int, time_str.split(':'))
    return datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=minute))
```

## Acceptance Criteria

- [ ] Stations can be created with name, playlist, and mode (shuffle/queue)
- [ ] Active station can be switched (only one active at a time)
- [ ] Time ranges can be added to meta-stations
- [ ] Daily schedule builder creates boundary-aware playlist
- [ ] Long tracks (>5 min overshoot) are swapped with shorter ones when available
- [ ] YouTube/SoundCloud tracks get 3-second padding for load gap
- [ ] Schedule is stored in `daily_schedule` table
- [ ] `get_now_playing()` returns correct track for any timestamp

## Dependencies

- Requires: **02-radio-data-model.md** (tables must exist)

## Testing

```python
def test_boundary_aware_scheduling():
    """Verify long tracks are swapped near boundaries."""
    # Create station with 17:00-20:00 range (3 hours)
    # Add playlist with mix of 5-min and 20-min tracks
    schedule = build_daily_schedule(station_id=1, target_date=date.today())

    # Check last track in range doesn't overshoot by >5 min
    last_track = schedule[-1]
    overshoot = (last_track.scheduled_end - datetime(..., 20, 0, 0)).total_seconds()
    assert overshoot <= 300, f"Overshoot {overshoot}s exceeds 5 min"


def test_deterministic_shuffle():
    """Same date produces same shuffle order."""
    schedule1 = build_daily_schedule(station_id=1, target_date=date(2026, 1, 15))
    schedule2 = build_daily_schedule(station_id=1, target_date=date(2026, 1, 15))

    track_ids1 = [s.track_id for s in schedule1]
    track_ids2 = [s.track_id for s in schedule2]
    assert track_ids1 == track_ids2, "Shuffle not deterministic"
```
