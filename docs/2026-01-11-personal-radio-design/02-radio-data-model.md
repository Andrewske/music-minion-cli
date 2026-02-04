# Radio Data Model

## Files to Modify/Create
- `src/music_minion/core/database.py` (modify - add radio tables to schema)
- `src/music_minion/domain/radio/models.py` (new)

## Implementation Details

Add radio-specific database tables to PostgreSQL schema. These tables extend the existing music-minion playlist system.

### Schema Addition

Add to `database.py` migration sequence (new version 27):

```sql
-- Station = playlist + radio metadata
CREATE TABLE IF NOT EXISTS stations (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    playlist_id     INTEGER REFERENCES playlists(id),
    mode            TEXT NOT NULL CHECK (mode IN ('shuffle', 'queue')),
    is_active       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_stations_active ON stations(is_active) WHERE is_active = TRUE;

-- Time ranges for meta-stations (like Main)
CREATE TABLE IF NOT EXISTS station_schedule (
    id              SERIAL PRIMARY KEY,
    station_id      INTEGER REFERENCES stations(id) ON DELETE CASCADE,
    start_time      TEXT NOT NULL,  -- "06:00" format
    end_time        TEXT NOT NULL,  -- "09:00" format
    target_station  INTEGER REFERENCES stations(id),
    position        INTEGER,
    CHECK (start_time < end_time OR (start_time > end_time)) -- Allow midnight wrap
);

CREATE INDEX idx_station_schedule_station ON station_schedule(station_id);

-- Playback history
CREATE TABLE IF NOT EXISTS radio_history (
    id              SERIAL PRIMARY KEY,
    station_id      INTEGER REFERENCES stations(id),
    track_id        INTEGER REFERENCES tracks(id),
    source_type     TEXT,
    source_url      TEXT,  -- Permanent URL like 'https://youtube.com/watch?v=ID'
    started_at      TIMESTAMP DEFAULT NOW(),
    ended_at        TIMESTAMP,
    position_ms     INTEGER
);

CREATE INDEX idx_radio_history_station ON radio_history(station_id, started_at DESC);
CREATE INDEX idx_radio_history_track ON radio_history(track_id);

-- Current playback state
CREATE TABLE IF NOT EXISTS radio_state (
    id              SERIAL PRIMARY KEY CHECK (id = 1),  -- Singleton
    active_station  INTEGER REFERENCES stations(id),
    started_at      TIMESTAMP,
    last_track_id   INTEGER,
    last_position   INTEGER
);

-- Pre-computed daily schedule
CREATE TABLE IF NOT EXISTS daily_schedule (
    id              SERIAL PRIMARY KEY,
    station_id      INTEGER REFERENCES stations(id),
    date            DATE NOT NULL,
    track_id        INTEGER REFERENCES tracks(id),
    source_type     TEXT,
    source_url      TEXT,
    scheduled_start TIMESTAMP NOT NULL,
    scheduled_end   TIMESTAMP NOT NULL,
    position        INTEGER NOT NULL,
    time_range_id   INTEGER REFERENCES station_schedule(id),
    UNIQUE(station_id, date, position)
);

CREATE INDEX idx_daily_schedule_lookup ON daily_schedule(station_id, date, scheduled_start, scheduled_end);

-- Session-level skipped tracks
CREATE TABLE IF NOT EXISTS radio_skipped (
    id              SERIAL PRIMARY KEY,
    station_id      INTEGER REFERENCES stations(id),
    track_id        INTEGER,
    source_url      TEXT,
    skipped_at      TIMESTAMP DEFAULT NOW(),
    reason          TEXT,
    UNIQUE(station_id, track_id, DATE(skipped_at))
);

CREATE INDEX idx_radio_skipped_lookup ON radio_skipped(station_id, DATE(skipped_at));
```

### Domain Models

```python
# src/music_minion/domain/radio/models.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Station:
    id: int
    name: str
    playlist_id: int
    mode: str  # 'shuffle' | 'queue'
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class StationSchedule:
    id: int
    station_id: int
    start_time: str  # "06:00"
    end_time: str    # "09:00"
    target_station: int
    position: int


@dataclass
class ScheduledTrack:
    id: int
    station_id: int
    date: datetime.date
    track_id: int
    source_type: str
    source_url: str
    scheduled_start: datetime
    scheduled_end: datetime
    position: int
    time_range_id: int


@dataclass
class NowPlaying:
    track: 'Track'
    position_ms: int
    next_track: Optional['Track']
    upcoming: list['Track']  # Next 5 tracks
```

## Acceptance Criteria

- [ ] All radio tables created in PostgreSQL
- [ ] Foreign key constraints properly reference existing tables (playlists, tracks)
- [ ] Indexes created for common query patterns (schedule lookup, history filtering)
- [ ] Models defined with proper type hints
- [ ] Schema version incremented to 27
- [ ] Migration tested from v26 to v27

## Dependencies

- Requires: **01-postgresql-migration.md** (PostgreSQL must be in place)

## Testing

```python
def test_radio_schema():
    """Verify radio tables exist with correct structure."""
    with get_db_connection() as conn:
        # Check tables exist
        tables = ['stations', 'station_schedule', 'radio_history',
                  'radio_state', 'daily_schedule', 'radio_skipped']
        for table in tables:
            result = conn.execute(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)",
                (table,)
            )
            assert result.fetchone()[0], f"Table {table} not found"

        # Check foreign keys
        result = conn.execute("""
            SELECT constraint_name FROM information_schema.table_constraints
            WHERE table_name = 'stations' AND constraint_type = 'FOREIGN KEY'
        """)
        assert result.rowcount > 0, "stations table missing foreign keys"
```
