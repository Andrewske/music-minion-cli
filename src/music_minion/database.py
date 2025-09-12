"""
SQLite database operations for Music Minion CLI
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from contextlib import contextmanager

from .config import Config, get_data_dir


# Database schema version for migrations
SCHEMA_VERSION = 1


def get_database_path() -> Path:
    """Get the path to the SQLite database file."""
    return get_data_dir() / "music_minion.db"


@contextmanager
def get_db_connection():
    """Get a database connection with proper cleanup."""
    db_path = get_database_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    try:
        yield conn
    finally:
        conn.close()


def init_database() -> None:
    """Initialize the database with required tables."""
    db_path = get_database_path()
    
    # Ensure data directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    with get_db_connection() as conn:
        # Create schema version table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            )
        """)
        
        # Create tracks table for basic track info
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                title TEXT,
                artist TEXT,
                album TEXT,
                genre TEXT,
                year INTEGER,
                duration REAL,
                key_signature TEXT,
                bpm REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create ratings table for user feedback
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL,
                rating_type TEXT NOT NULL, -- 'archive', 'skip', 'like', 'love'
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                hour_of_day INTEGER,
                day_of_week INTEGER, -- 0=Monday, 6=Sunday
                context TEXT, -- Additional context info
                FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE
            )
        """)
        
        # Create notes table for user notes on tracks
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL,
                note_text TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_by_ai BOOLEAN DEFAULT FALSE,
                ai_tags TEXT, -- JSON array of AI-extracted tags
                FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE
            )
        """)
        
        # Create playback_sessions table for tracking listening sessions
        conn.execute("""
            CREATE TABLE IF NOT EXISTS playback_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                completed BOOLEAN DEFAULT FALSE, -- Did the track play to completion?
                skipped_at_percent REAL, -- If skipped, at what percentage?
                FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_file_path ON tracks (file_path)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks (artist)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ratings_track_id ON ratings (track_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ratings_timestamp ON ratings (timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ratings_type ON ratings (rating_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_track_id ON notes (track_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_track_id ON playback_sessions (track_id)")
        
        # Set schema version
        conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        
        conn.commit()


def get_or_create_track(file_path: str, title: Optional[str] = None, 
                       artist: Optional[str] = None, album: Optional[str] = None,
                       genre: Optional[str] = None, year: Optional[int] = None,
                       duration: Optional[float] = None, key_signature: Optional[str] = None,
                       bpm: Optional[float] = None) -> int:
    """Get track ID if exists, otherwise create new track record."""
    with get_db_connection() as conn:
        # Try to find existing track
        cursor = conn.execute("SELECT id FROM tracks WHERE file_path = ?", (file_path,))
        row = cursor.fetchone()
        
        if row:
            # Update existing track with any new metadata
            conn.execute("""
                UPDATE tracks SET
                    title = COALESCE(?, title),
                    artist = COALESCE(?, artist),
                    album = COALESCE(?, album),
                    genre = COALESCE(?, genre),
                    year = COALESCE(?, year),
                    duration = COALESCE(?, duration),
                    key_signature = COALESCE(?, key_signature),
                    bpm = COALESCE(?, bpm),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (title, artist, album, genre, year, duration, key_signature, bpm, row['id']))
            conn.commit()
            return row['id']
        else:
            # Create new track
            cursor = conn.execute("""
                INSERT INTO tracks (file_path, title, artist, album, genre, year, duration, key_signature, bpm)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (file_path, title, artist, album, genre, year, duration, key_signature, bpm))
            conn.commit()
            return cursor.lastrowid


def add_rating(track_id: int, rating_type: str, context: Optional[str] = None) -> None:
    """Add a rating for a track."""
    now = datetime.now()
    hour_of_day = now.hour
    day_of_week = now.weekday()  # 0=Monday, 6=Sunday
    
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO ratings (track_id, rating_type, hour_of_day, day_of_week, context)
            VALUES (?, ?, ?, ?, ?)
        """, (track_id, rating_type, hour_of_day, day_of_week, context))
        conn.commit()


def add_note(track_id: int, note_text: str) -> int:
    """Add a note for a track and return note ID."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO notes (track_id, note_text)
            VALUES (?, ?)
        """, (track_id, note_text))
        conn.commit()
        return cursor.lastrowid


def start_playback_session(track_id: int) -> int:
    """Start a playback session and return session ID."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO playback_sessions (track_id)
            VALUES (?)
        """, (track_id,))
        conn.commit()
        return cursor.lastrowid


def end_playback_session(session_id: int, completed: bool = False, 
                        skipped_at_percent: Optional[float] = None) -> None:
    """End a playback session."""
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE playback_sessions SET
                ended_at = CURRENT_TIMESTAMP,
                completed = ?,
                skipped_at_percent = ?
            WHERE id = ?
        """, (completed, skipped_at_percent, session_id))
        conn.commit()


def get_track_ratings(track_id: int) -> List[Dict[str, Any]]:
    """Get all ratings for a track."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT rating_type, timestamp, hour_of_day, day_of_week, context
            FROM ratings 
            WHERE track_id = ?
            ORDER BY timestamp DESC
        """, (track_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_track_notes(track_id: int) -> List[Dict[str, Any]]:
    """Get all notes for a track."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT note_text, timestamp, processed_by_ai, ai_tags
            FROM notes 
            WHERE track_id = ?
            ORDER BY timestamp DESC
        """, (track_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_recent_ratings(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent ratings across all tracks."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT r.rating_type, r.timestamp, r.context,
                   t.title, t.artist, t.file_path
            FROM ratings r
            JOIN tracks t ON r.track_id = t.id
            ORDER BY r.timestamp DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def get_archived_tracks() -> List[int]:
    """Get list of track IDs that have been archived."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT DISTINCT track_id
            FROM ratings
            WHERE rating_type = 'archive'
        """)
        return [row['track_id'] for row in cursor.fetchall()]


def get_rating_patterns(track_id: int) -> Dict[str, Any]:
    """Get rating patterns for a track (time-based preferences)."""
    with get_db_connection() as conn:
        # Get hourly preferences
        cursor = conn.execute("""
            SELECT hour_of_day, rating_type, COUNT(*) as count
            FROM ratings
            WHERE track_id = ?
            GROUP BY hour_of_day, rating_type
            ORDER BY hour_of_day, count DESC
        """, (track_id,))
        hourly_patterns = {}
        for row in cursor.fetchall():
            hour = row['hour_of_day']
            if hour not in hourly_patterns:
                hourly_patterns[hour] = []
            hourly_patterns[hour].append({
                'rating': row['rating_type'],
                'count': row['count']
            })
        
        # Get daily preferences
        cursor = conn.execute("""
            SELECT day_of_week, rating_type, COUNT(*) as count
            FROM ratings
            WHERE track_id = ?
            GROUP BY day_of_week, rating_type
            ORDER BY day_of_week, count DESC
        """, (track_id,))
        daily_patterns = {}
        for row in cursor.fetchall():
            day = row['day_of_week']
            if day not in daily_patterns:
                daily_patterns[day] = []
            daily_patterns[day].append({
                'rating': row['rating_type'],
                'count': row['count']
            })
        
        return {
            'hourly': hourly_patterns,
            'daily': daily_patterns
        }


def get_library_analytics() -> Dict[str, Any]:
    """Get analytics about the music library and ratings."""
    with get_db_connection() as conn:
        # Basic counts
        cursor = conn.execute("SELECT COUNT(*) as count FROM tracks")
        total_tracks = cursor.fetchone()['count']
        
        cursor = conn.execute("SELECT COUNT(*) as count FROM ratings")
        total_ratings = cursor.fetchone()['count']
        
        cursor = conn.execute("SELECT COUNT(DISTINCT track_id) as count FROM ratings")
        rated_tracks = cursor.fetchone()['count']
        
        # Rating type distribution
        cursor = conn.execute("""
            SELECT rating_type, COUNT(*) as count
            FROM ratings
            GROUP BY rating_type
            ORDER BY count DESC
        """)
        rating_distribution = {row['rating_type']: row['count'] for row in cursor.fetchall()}
        
        # Most active hours
        cursor = conn.execute("""
            SELECT hour_of_day, COUNT(*) as count
            FROM ratings
            GROUP BY hour_of_day
            ORDER BY count DESC
            LIMIT 5
        """)
        active_hours = [{'hour': row['hour_of_day'], 'count': row['count']} 
                       for row in cursor.fetchall()]
        
        # Most active days
        cursor = conn.execute("""
            SELECT day_of_week, COUNT(*) as count
            FROM ratings
            GROUP BY day_of_week
            ORDER BY count DESC
            LIMIT 7
        """)
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        active_days = [{'day': day_names[row['day_of_week']], 'count': row['count']} 
                      for row in cursor.fetchall()]
        
        return {
            'total_tracks': total_tracks,
            'total_ratings': total_ratings,
            'rated_tracks': rated_tracks,
            'rating_distribution': rating_distribution,
            'active_hours': active_hours,
            'active_days': active_days
        }


def cleanup_old_sessions() -> None:
    """Clean up old uncompleted playback sessions."""
    with get_db_connection() as conn:
        # Remove sessions older than 24 hours that weren't properly ended
        conn.execute("""
            DELETE FROM playback_sessions 
            WHERE ended_at IS NULL 
            AND started_at < datetime('now', '-24 hours')
        """)
        conn.commit()


def get_track_by_path(file_path: str) -> Optional[Dict[str, Any]]:
    """Get track information by file path."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM tracks WHERE file_path = ?
        """, (file_path,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_ai_processed_note(note_id: int, ai_tags: str) -> None:
    """Mark a note as processed by AI and store extracted tags."""
    with get_db_connection() as conn:
        conn.execute("""
            UPDATE notes SET
                processed_by_ai = TRUE,
                ai_tags = ?
            WHERE id = ?
        """, (ai_tags, note_id))
        conn.commit()


def get_unprocessed_notes() -> List[Dict[str, Any]]:
    """Get notes that haven't been processed by AI yet."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT n.id, n.note_text, n.timestamp,
                   t.title, t.artist, t.file_path
            FROM notes n
            JOIN tracks t ON n.track_id = t.id
            WHERE n.processed_by_ai = FALSE
            ORDER BY n.timestamp ASC
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_all_tracks() -> List[Dict[str, Any]]:
    """Get all tracks from the database."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM tracks
            ORDER BY artist, album, title
        """)
        return [dict(row) for row in cursor.fetchall()]


def get_available_track_paths() -> List[str]:
    """Get file paths of tracks that are not archived."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT t.file_path
            FROM tracks t
            LEFT JOIN ratings r ON t.id = r.track_id AND r.rating_type = 'archive'
            WHERE r.id IS NULL
            ORDER BY t.artist, t.album, t.title
        """)
        return [row['file_path'] for row in cursor.fetchall()]


def get_available_tracks() -> List[Dict[str, Any]]:
    """Get all tracks that are not archived."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT t.*
            FROM tracks t
            LEFT JOIN ratings r ON t.id = r.track_id AND r.rating_type = 'archive'
            WHERE r.id IS NULL
            ORDER BY t.artist, t.album, t.title
        """)
        return [dict(row) for row in cursor.fetchall()]


def db_track_to_library_track(db_track: Dict[str, Any]):
    """Convert database track record to library.Track object."""
    # Import here to avoid circular imports
    from . import library
    
    return library.Track(
        file_path=db_track['file_path'],
        title=db_track['title'],
        artist=db_track['artist'],
        album=db_track['album'],
        genre=db_track['genre'],
        year=db_track['year'],
        duration=db_track['duration'],
        bitrate=None,  # Not stored in database yet
        file_size=0,   # Not stored in database yet
        format=None,   # Could derive from file_path
        key=db_track['key_signature'],
        bpm=db_track['bpm']
    )