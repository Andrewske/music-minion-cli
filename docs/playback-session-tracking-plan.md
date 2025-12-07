# Playback Session Tracking Plan

## Objectives
- Measure **time listened** for every track with second-level accuracy
- Count **sessions** (one per track playback) for play count metrics
- Calculate **effective plays** as `total_seconds / track_duration` at query time
- Keep tracking crash-resilient by persisting progress each tick

## Session Definition
- A **session** begins when a track starts playing and ends when playback switches or stops
- Pause/resume keeps the same session alive
- Every second of playback counts (including replays/rewinds)
- One active session per playback source at a time

## Data Model

### `track_listen_sessions`
```sql
CREATE TABLE track_listen_sessions (
    session_id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    play_date DATE NOT NULL,
    playlist_id INTEGER NULL,
    seconds_played REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (track_id) REFERENCES tracks(id)
);

CREATE INDEX idx_sessions_track ON track_listen_sessions(track_id);
CREATE INDEX idx_sessions_date ON track_listen_sessions(play_date);
```

## Update Logic

### 1. Start Session
```python
def on_track_start(track_id: int, playlist_id: int | None) -> int:
    cursor = db.execute("""
        INSERT INTO track_listen_sessions (track_id, play_date, playlist_id)
        VALUES (?, DATE('now'), ?)
    """, (track_id, playlist_id))
    return cursor.lastrowid
```

### 2. Per-Second Tick
```python
def on_tick(session_id: int, is_playing: bool):
    if is_playing:
        db.execute("""
            UPDATE track_listen_sessions
            SET seconds_played = seconds_played + 1
            WHERE session_id = ?
        """, (session_id,))
```

### 3. Track Change / Stop
No action needed—session is complete as-is.

## Query Patterns

```sql
-- Track stats with effective plays
SELECT
    COUNT(*) as play_count,
    SUM(s.seconds_played) as total_seconds,
    SUM(s.seconds_played) / t.duration as effective_plays,
    MAX(s.started_at) as last_played
FROM track_listen_sessions s
JOIN tracks t ON t.id = s.track_id
WHERE s.track_id = ?;

-- Daily listening time
SELECT SUM(seconds_played)
FROM track_listen_sessions
WHERE play_date = DATE('now');

-- Top tracks by listening time (last 30 days)
SELECT s.track_id, SUM(s.seconds_played) as total
FROM track_listen_sessions s
WHERE s.play_date >= DATE('now', '-30 days')
GROUP BY s.track_id
ORDER BY total DESC
LIMIT 20;

-- Playlist listening stats
SELECT playlist_id, COUNT(*) as sessions, SUM(seconds_played) as time
FROM track_listen_sessions
WHERE playlist_id IS NOT NULL
GROUP BY playlist_id;
```

## Performance
- 1 write/second is trivial for SQLite with WAL mode
- No pre-aggregated tables needed—GROUP BY at query time is fast enough
- Crashes lose at most 1 second of data

## Testing Strategy
- **Counter increment**: verify `seconds_played` increases by 1 per tick while playing
- **Pause behavior**: confirm counter stops during pause
- **Session lifecycle**: new session per track start
- **Query correctness**: verify aggregations match expected values
