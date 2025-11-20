"""
SQLite database operations for Music Minion CLI
"""

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import get_data_dir

logger = logging.getLogger(__name__)


# Database schema version for migrations
SCHEMA_VERSION = 17


def get_database_path() -> Path:
    """Get the path to the SQLite database file."""
    return get_data_dir() / "music_minion.db"


@contextmanager
def get_db_connection():
    """Get a database connection with proper cleanup and concurrency support."""
    db_path = get_database_path()
    # Timeout increased to 30s to handle long-running operations (e.g., playlist sync)
    # WAL mode enables concurrent reads during writes
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row  # Enable dict-like access

    # Enable WAL mode for better concurrency (allows reads during writes)
    conn.execute("PRAGMA journal_mode=WAL")

    try:
        yield conn
    finally:
        conn.close()


def migrate_database(conn, current_version: int) -> None:
    """Migrate database from current_version to latest schema."""
    if current_version < 3:
        # Migration from v2 to v3: Add playlist tables
        conn.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL, -- 'manual' or 'smart'
                description TEXT,
                track_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS playlist_tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL,
                track_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE,
                FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE,
                UNIQUE (playlist_id, track_id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS playlist_filters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL,
                field TEXT NOT NULL, -- 'title', 'artist', 'album', 'genre', 'year', 'bpm', 'key'
                operator TEXT NOT NULL, -- 'contains', 'starts_with', 'ends_with', 'equals', 'not_equals', 'gt', 'lt', 'gte', 'lte'
                value TEXT NOT NULL,
                conjunction TEXT NOT NULL DEFAULT 'AND', -- 'AND' or 'OR' for combining with next filter
                FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS active_playlist (
                id INTEGER PRIMARY KEY CHECK (id = 1), -- Ensure only one row
                playlist_id INTEGER,
                activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE SET NULL
            )
        """)

        # Create indexes for playlist performance
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_playlist_tracks_playlist_id ON playlist_tracks (playlist_id, position)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_playlist_tracks_track_id ON playlist_tracks (track_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_playlist_filters_playlist_id ON playlist_filters (playlist_id)"
        )

        # Create indexes on tracks table for smart playlist filtering performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_year ON tracks (year)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_album ON tracks (album)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_genre ON tracks (genre)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_bpm ON tracks (bpm)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tracks_key ON tracks (key_signature)"
        )

        conn.commit()

    if current_version < 4:
        # Migration from v3 to v4: Add track_count column and fix conjunction constraint
        # Add track_count column to playlists table
        try:
            conn.execute(
                "ALTER TABLE playlists ADD COLUMN track_count INTEGER DEFAULT 0"
            )
        except Exception:
            # Column might already exist if user is on modified v3
            pass

        # Initialize track_count for existing playlists
        # For manual playlists, count actual tracks
        conn.execute("""
            UPDATE playlists
            SET track_count = (
                SELECT COUNT(*)
                FROM playlist_tracks
                WHERE playlist_tracks.playlist_id = playlists.id
            )
            WHERE type = 'manual'
        """)

        # For smart playlists, set to 0 initially (will be updated when they view/use them)
        conn.execute("""
            UPDATE playlists
            SET track_count = 0
            WHERE type = 'smart'
        """)

        conn.commit()

    if current_version < 5:
        # Migration from v4 to v5: Add playback state and position tracking (Phase 6)

        # Create playback_state table for global shuffle mode
        conn.execute("""
            CREATE TABLE IF NOT EXISTS playback_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                shuffle_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Initialize playback state with shuffle enabled (default behavior)
        conn.execute("""
            INSERT OR IGNORE INTO playback_state (id, shuffle_enabled)
            VALUES (1, TRUE)
        """)

        # Add position tracking columns to active_playlist table
        try:
            conn.execute(
                "ALTER TABLE active_playlist ADD COLUMN last_played_track_id INTEGER"
            )
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise  # Re-raise if it's not a "column exists" error

        try:
            conn.execute(
                "ALTER TABLE active_playlist ADD COLUMN last_played_position INTEGER"
            )
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        try:
            conn.execute(
                "ALTER TABLE active_playlist ADD COLUMN last_played_at TIMESTAMP"
            )
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # Add foreign key constraint note: SQLite doesn't support ADD CONSTRAINT after table creation
        # The FK constraint for last_played_track_id will be enforced by application logic

        conn.commit()

    if current_version < 6:
        # Migration from v5 to v6: Add index for position tracking performance
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_active_playlist_track
            ON active_playlist(last_played_track_id)
        """)

        conn.commit()

    if current_version < 7:
        # Migration from v6 to v7: Add sync tracking columns (Phase 7)

        # Add file modification time tracking
        # Note: Declared as INTEGER but stores floats for sub-second precision
        # SQLite's dynamic typing handles this automatically
        try:
            conn.execute("ALTER TABLE tracks ADD COLUMN file_mtime INTEGER")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # Add last sync timestamp
        try:
            conn.execute("ALTER TABLE tracks ADD COLUMN last_synced_at TIMESTAMP")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # Create index for quick change detection
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tracks_mtime
            ON tracks(file_mtime)
        """)

        conn.commit()

    if current_version < 8:
        # Migration from v7 to v8: Add last_played_at tracking to playlists

        try:
            conn.execute("ALTER TABLE playlists ADD COLUMN last_played_at TIMESTAMP")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # Create index for sorting by recently played
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_playlists_last_played
            ON playlists(last_played_at DESC)
        """)

        conn.commit()

    if current_version < 9:
        # Migration from v8 to v9: Add reasoning field for AI tag explanations

        try:
            conn.execute("ALTER TABLE tags ADD COLUMN reasoning TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        conn.commit()

    if current_version < 10:
        # Migration from v9 to v10: Add remix_artist field for DJ metadata

        try:
            conn.execute("ALTER TABLE tracks ADD COLUMN remix_artist TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        conn.commit()

    if current_version < 11:
        # Migration from v10 to v11: Multi-provider support
        # Add local_path column and provider ID columns

        # 1. Add new local_path column
        try:
            conn.execute("ALTER TABLE tracks ADD COLUMN local_path TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # 2. Add provider ID columns (nullable, UNIQUE constraint added via index below)
        try:
            conn.execute("ALTER TABLE tracks ADD COLUMN soundcloud_id TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        try:
            conn.execute("ALTER TABLE tracks ADD COLUMN spotify_id TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        try:
            conn.execute("ALTER TABLE tracks ADD COLUMN youtube_id TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # 4. Add sync timestamp columns
        try:
            conn.execute("ALTER TABLE tracks ADD COLUMN soundcloud_synced_at TIMESTAMP")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        try:
            conn.execute("ALTER TABLE tracks ADD COLUMN spotify_synced_at TIMESTAMP")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        try:
            conn.execute("ALTER TABLE tracks ADD COLUMN youtube_synced_at TIMESTAMP")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # 5. Create provider_state table for auth and config
        conn.execute("""
            CREATE TABLE IF NOT EXISTS provider_state (
                provider TEXT PRIMARY KEY,
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                authenticated BOOLEAN NOT NULL DEFAULT FALSE,
                last_sync_at TIMESTAMP,
                auth_data TEXT,      -- JSON: OAuth tokens
                config TEXT,          -- JSON: provider-specific settings
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 6. Initialize provider_state for local provider
        conn.execute("""
            INSERT OR IGNORE INTO provider_state (provider, enabled, authenticated)
            VALUES ('local', TRUE, TRUE)
        """)

        # 7. Create active_library table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS active_library (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                provider TEXT NOT NULL DEFAULT 'local',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 8. Initialize active_library
        conn.execute("""
            INSERT OR IGNORE INTO active_library (id, provider)
            VALUES (1, 'local')
        """)

        # 9. Create index on local_path (same as old file_path index)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tracks_local_path ON tracks (local_path)"
        )

        # 10. Create UNIQUE indexes on provider IDs for fast lookups and uniqueness
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_tracks_soundcloud_id ON tracks (soundcloud_id) WHERE soundcloud_id IS NOT NULL"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_tracks_spotify_id ON tracks (spotify_id) WHERE spotify_id IS NOT NULL"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_tracks_youtube_id ON tracks (youtube_id) WHERE youtube_id IS NOT NULL"
        )

        conn.commit()

    if current_version < 12:
        # Migration from v11 to v12: Add source tracking and playlist provider IDs

        # 1. Add source column to tracks table (single provider per track)
        try:
            conn.execute("ALTER TABLE tracks ADD COLUMN source TEXT DEFAULT 'local'")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # 2. Set source='local' for all existing tracks (they're all local files)
        conn.execute("UPDATE tracks SET source = 'local' WHERE source IS NULL")

        # 3. Create index on source for filtering by provider
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_source ON tracks (source)")

        # 4. Add provider playlist ID columns to playlists table
        try:
            conn.execute("ALTER TABLE playlists ADD COLUMN soundcloud_playlist_id TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        try:
            conn.execute("ALTER TABLE playlists ADD COLUMN spotify_playlist_id TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # 5. Add last_track_count for incremental playlist sync
        try:
            conn.execute(
                "ALTER TABLE playlists ADD COLUMN last_track_count INTEGER DEFAULT 0"
            )
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # 6. Create unique indexes on provider playlist IDs
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_playlists_soundcloud_id ON playlists (soundcloud_playlist_id) WHERE soundcloud_playlist_id IS NOT NULL"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_playlists_spotify_id ON playlists (spotify_playlist_id) WHERE spotify_playlist_id IS NOT NULL"
        )

        conn.commit()

    if current_version < 13:
        # Migration from v12 to v13: Removed file_path column cleanup (now handled in v14)
        # This migration is kept for historical compatibility but does nothing
        print("  Skipping v13 migration (superseded by v14)")
        conn.commit()

    if current_version < 14:
        # Migration from v13 to v14: Remove file_path column (backward compatibility cleanup)
        # Keep only local_path column since we're the only user

        print("  Migrating to v14: Removing file_path column...")

        # Commit any pending operations
        conn.commit()

        # Step 1: Disable foreign keys during table recreation
        conn.execute("PRAGMA foreign_keys=OFF")

        # Step 2: Copy any remaining file_path data to local_path (safety measure)
        # This may fail if file_path column doesn't exist (already migrated)
        try:
            conn.execute(
                "UPDATE tracks SET local_path = file_path WHERE local_path IS NULL AND file_path IS NOT NULL"
            )
        except sqlite3.OperationalError as e:
            if "no such column" not in str(e).lower():
                raise
            # file_path column doesn't exist, which is fine

        # Step 3: Create new tracks table without file_path column
        conn.execute("""
            CREATE TABLE tracks_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                artist TEXT,
                album TEXT,
                genre TEXT,
                year INTEGER,
                duration REAL,
                key_signature TEXT,
                bpm REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_mtime INTEGER,
                last_synced_at TIMESTAMP,
                remix_artist TEXT,
                local_path TEXT,
                soundcloud_id TEXT,
                spotify_id TEXT,
                youtube_id TEXT,
                soundcloud_synced_at TIMESTAMP,
                spotify_synced_at TIMESTAMP,
                youtube_synced_at TIMESTAMP,
                source TEXT DEFAULT 'local'
            )
        """)

        # Step 4: Copy all data from old table (excluding file_path)
        conn.execute("""
            INSERT INTO tracks_new (
                id, title, artist, album, genre, year, duration,
                key_signature, bpm, created_at, updated_at, file_mtime,
                last_synced_at, remix_artist, local_path, soundcloud_id,
                spotify_id, youtube_id, soundcloud_synced_at, spotify_synced_at,
                youtube_synced_at, source
            )
            SELECT
                id, title, artist, album, genre, year, duration,
                key_signature, bpm, created_at, updated_at, file_mtime,
                last_synced_at, remix_artist, local_path, soundcloud_id,
                spotify_id, youtube_id, soundcloud_synced_at, spotify_synced_at,
                youtube_synced_at, source
            FROM tracks
        """)

        # Step 5: Drop old table
        conn.execute("DROP TABLE tracks")

        # Step 6: Rename new table
        conn.execute("ALTER TABLE tracks_new RENAME TO tracks")

        # Step 7: Recreate all indexes (12 total, excluding idx_tracks_file_path)
        # Regular indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks (artist)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_year ON tracks (year)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_album ON tracks (album)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_genre ON tracks (genre)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_bpm ON tracks (bpm)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tracks_key ON tracks (key_signature)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tracks_mtime ON tracks (file_mtime)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tracks_local_path ON tracks (local_path)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_source ON tracks (source)")

        # Partial UNIQUE indexes
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_tracks_soundcloud_id ON tracks (soundcloud_id) WHERE soundcloud_id IS NOT NULL"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_tracks_spotify_id ON tracks (spotify_id) WHERE spotify_id IS NOT NULL"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_tracks_youtube_id ON tracks (youtube_id) WHERE youtube_id IS NOT NULL"
        )

        # Step 8: Re-enable foreign keys
        conn.execute("PRAGMA foreign_keys=ON")

        print("  ✓ Migration to v14 complete: file_path column removed")
        conn.commit()

    if current_version < 15:
        # Migration from v14 to v15: Add playlist sync timestamps
        print("  Migrating to v15: Adding playlist sync timestamps...")

        # Add last_synced_at column
        try:
            conn.execute("ALTER TABLE playlists ADD COLUMN last_synced_at TIMESTAMP")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # Add provider_last_modified column
        try:
            conn.execute("ALTER TABLE playlists ADD COLUMN provider_last_modified TIMESTAMP")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        print("  ✓ Migration to v15 complete: Playlist sync timestamps added")
        conn.commit()

    if current_version < 16:
        # Migration from v15 to v16: Add provider_created_at for sorting playlists by creation date

        # Add provider_created_at column to track when playlists were created on the provider (e.g., SoundCloud)
        try:
            conn.execute("ALTER TABLE playlists ADD COLUMN provider_created_at TIMESTAMP")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        print("  ✓ Migration to v16 complete: Added provider_created_at column")
        conn.commit()

    if current_version < 17:
        # Migration from v16 to v17: Add source tracking to ratings for provider likes
        print("  Migrating to v17: Adding source tracking to ratings...")

        # Add source column to ratings table (user, soundcloud, spotify, youtube)
        try:
            conn.execute("ALTER TABLE ratings ADD COLUMN source TEXT DEFAULT 'user'")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # Set source='user' for all existing ratings (they're all user ratings)
        conn.execute("UPDATE ratings SET source = 'user' WHERE source IS NULL")

        # Create index for fast lookups (has_soundcloud_like queries)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ratings_track_source ON ratings (track_id, source)"
        )

        print("  ✓ Migration to v17 complete: Source tracking added to ratings")
        conn.commit()


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
                local_path TEXT,
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

        # Create tags table for AI and user tags
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL,
                tag_name TEXT NOT NULL,
                source TEXT NOT NULL, -- 'user' | 'ai'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confidence REAL, -- AI confidence score (0.0-1.0)
                blacklisted BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE
            )
        """)

        # Create ai_requests table for token usage tracking
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL,
                request_type TEXT NOT NULL, -- 'auto_analysis' | 'manual_analysis'
                model_name TEXT DEFAULT 'gpt-4o-mini',
                prompt_tokens INTEGER,
                completion_tokens INTEGER,
                total_tokens INTEGER,
                cost_estimate REAL, -- Calculated cost in USD
                request_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                response_time_ms INTEGER,
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT,
                FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE
            )
        """)

        # Create indexes for performance
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tracks_local_path ON tracks (local_path)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks (artist)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ratings_track_id ON ratings (track_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ratings_timestamp ON ratings (timestamp)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ratings_type ON ratings (rating_type)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_notes_track_id ON notes (track_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_track_id ON playback_sessions (track_id)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tags_track_id ON tags (track_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tags_name ON tags (tag_name)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tags_source ON tags (source)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ai_requests_track_id ON ai_requests (track_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ai_requests_timestamp ON ai_requests (request_timestamp)"
        )

        # Check current schema version and run migrations if needed
        # Use MAX to handle legacy databases with multiple version rows
        cursor = conn.execute("SELECT MAX(version) as version FROM schema_version")
        row = cursor.fetchone()
        current_version = row["version"] if row and row["version"] else 0
        cursor.close()  # Close cursor to release any locks before migration

        if current_version < SCHEMA_VERSION:
            migrate_database(conn, current_version)

        # Set schema version (delete old rows to prevent duplicates)
        conn.execute("DELETE FROM schema_version")
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )

        conn.commit()


def get_or_create_track(
    local_path: str,
    title: Optional[str] = None,
    artist: Optional[str] = None,
    remix_artist: Optional[str] = None,
    album: Optional[str] = None,
    genre: Optional[str] = None,
    year: Optional[int] = None,
    duration: Optional[float] = None,
    key_signature: Optional[str] = None,
    bpm: Optional[float] = None,
) -> int:
    """Get track ID if exists, otherwise create new track record."""
    with get_db_connection() as conn:
        # Try to find existing track by local_path
        cursor = conn.execute(
            """
            SELECT id FROM tracks
            WHERE local_path = ?
        """,
            (local_path,),
        )
        row = cursor.fetchone()

        if row:
            # Update existing track with any new metadata
            conn.execute(
                """
                UPDATE tracks SET
                    title = COALESCE(?, title),
                    artist = COALESCE(?, artist),
                    remix_artist = COALESCE(?, remix_artist),
                    album = COALESCE(?, album),
                    genre = COALESCE(?, genre),
                    year = COALESCE(?, year),
                    duration = COALESCE(?, duration),
                    key_signature = COALESCE(?, key_signature),
                    bpm = COALESCE(?, bpm),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (
                    title,
                    artist,
                    remix_artist,
                    album,
                    genre,
                    year,
                    duration,
                    key_signature,
                    bpm,
                    row["id"],
                ),
            )
            conn.commit()
            return row["id"]
        else:
            # Create new track
            cursor = conn.execute(
                """
                INSERT INTO tracks (local_path, title, artist, remix_artist, album, genre, year, duration, key_signature, bpm)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    local_path,
                    title,
                    artist,
                    remix_artist,
                    album,
                    genre,
                    year,
                    duration,
                    key_signature,
                    bpm,
                ),
            )
            conn.commit()
            return cursor.lastrowid


def add_rating(
    track_id: int,
    rating_type: str,
    context: Optional[str] = None,
    source: str = "user",
) -> None:
    """Add a rating for a track.

    Args:
        track_id: Track ID
        rating_type: Type of rating ('archive', 'skip', 'like', 'love')
        context: Optional context text
        source: Source of rating ('user', 'soundcloud', 'spotify', 'youtube')
    """
    now = datetime.now()
    hour_of_day = now.hour
    day_of_week = now.weekday()  # 0=Monday, 6=Sunday

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO ratings (track_id, rating_type, hour_of_day, day_of_week, context, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (track_id, rating_type, hour_of_day, day_of_week, context, source),
        )
        conn.commit()


def has_soundcloud_like(track_id: int) -> bool:
    """Check if track has a SoundCloud like marker.

    Args:
        track_id: Track ID

    Returns:
        True if track has source='soundcloud' rating
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT EXISTS(
                SELECT 1 FROM ratings
                WHERE track_id = ? AND source = 'soundcloud'
            )
        """,
            (track_id,),
        )
        return bool(cursor.fetchone()[0])


def batch_add_soundcloud_likes(track_ids: List[int]) -> int:
    """Bulk insert SoundCloud like markers for multiple tracks.

    Args:
        track_ids: List of track IDs to add markers for

    Returns:
        Number of markers created
    """
    if not track_ids:
        return 0

    now = datetime.now()
    hour_of_day = now.hour
    day_of_week = now.weekday()

    # Prepare batch insert data
    markers = [
        (track_id, "like", hour_of_day, day_of_week, "Synced from SoundCloud", "soundcloud")
        for track_id in track_ids
    ]

    with get_db_connection() as conn:
        # Use INSERT OR IGNORE to avoid duplicates
        conn.executemany(
            """
            INSERT OR IGNORE INTO ratings (track_id, rating_type, hour_of_day, day_of_week, context, source)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            markers,
        )
        inserted_count = conn.total_changes
        conn.commit()

    return inserted_count


def add_note(track_id: int, note_text: str) -> int:
    """Add a note for a track and return note ID."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO notes (track_id, note_text)
            VALUES (?, ?)
        """,
            (track_id, note_text),
        )
        conn.commit()
        return cursor.lastrowid


def start_playback_session(track_id: int) -> int:
    """Start a playback session and return session ID."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO playback_sessions (track_id)
            VALUES (?)
        """,
            (track_id,),
        )
        conn.commit()
        return cursor.lastrowid


def end_playback_session(
    session_id: int, completed: bool = False, skipped_at_percent: Optional[float] = None
) -> None:
    """End a playback session."""
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE playback_sessions SET
                ended_at = CURRENT_TIMESTAMP,
                completed = ?,
                skipped_at_percent = ?
            WHERE id = ?
        """,
            (completed, skipped_at_percent, session_id),
        )
        conn.commit()


def get_track_ratings(track_id: int) -> List[Dict[str, Any]]:
    """Get all ratings for a track."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT rating_type, timestamp, hour_of_day, day_of_week, context
            FROM ratings 
            WHERE track_id = ?
            ORDER BY timestamp DESC
        """,
            (track_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_track_notes(track_id: int) -> List[Dict[str, Any]]:
    """Get all notes for a track."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT note_text, timestamp, processed_by_ai, ai_tags
            FROM notes 
            WHERE track_id = ?
            ORDER BY timestamp DESC
        """,
            (track_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_recent_ratings(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent ratings across all tracks."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT r.rating_type, r.timestamp, r.context,
                   t.title, t.artist,
                   t.local_path
            FROM ratings r
            JOIN tracks t ON r.track_id = t.id
            ORDER BY r.timestamp DESC
            LIMIT ?
        """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_archived_tracks() -> List[int]:
    """Get list of track IDs that have been archived."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT DISTINCT track_id
            FROM ratings
            WHERE rating_type = 'archive'
        """)
        return [row["track_id"] for row in cursor.fetchall()]


def get_rating_patterns(track_id: int) -> Dict[str, Any]:
    """Get rating patterns for a track (time-based preferences)."""
    with get_db_connection() as conn:
        # Get hourly preferences
        cursor = conn.execute(
            """
            SELECT hour_of_day, rating_type, COUNT(*) as count
            FROM ratings
            WHERE track_id = ?
            GROUP BY hour_of_day, rating_type
            ORDER BY hour_of_day, count DESC
        """,
            (track_id,),
        )
        hourly_patterns = {}
        for row in cursor.fetchall():
            hour = row["hour_of_day"]
            if hour not in hourly_patterns:
                hourly_patterns[hour] = []
            hourly_patterns[hour].append(
                {"rating": row["rating_type"], "count": row["count"]}
            )

        # Get daily preferences
        cursor = conn.execute(
            """
            SELECT day_of_week, rating_type, COUNT(*) as count
            FROM ratings
            WHERE track_id = ?
            GROUP BY day_of_week, rating_type
            ORDER BY day_of_week, count DESC
        """,
            (track_id,),
        )
        daily_patterns = {}
        for row in cursor.fetchall():
            day = row["day_of_week"]
            if day not in daily_patterns:
                daily_patterns[day] = []
            daily_patterns[day].append(
                {"rating": row["rating_type"], "count": row["count"]}
            )

        return {"hourly": hourly_patterns, "daily": daily_patterns}


def get_library_analytics() -> Dict[str, Any]:
    """Get analytics about the music library and ratings."""
    with get_db_connection() as conn:
        # Basic counts
        cursor = conn.execute("SELECT COUNT(*) as count FROM tracks")
        total_tracks = cursor.fetchone()["count"]

        cursor = conn.execute("SELECT COUNT(*) as count FROM ratings")
        total_ratings = cursor.fetchone()["count"]

        cursor = conn.execute("SELECT COUNT(DISTINCT track_id) as count FROM ratings")
        rated_tracks = cursor.fetchone()["count"]

        # Rating type distribution
        cursor = conn.execute("""
            SELECT rating_type, COUNT(*) as count
            FROM ratings
            GROUP BY rating_type
            ORDER BY count DESC
        """)
        rating_distribution = {
            row["rating_type"]: row["count"] for row in cursor.fetchall()
        }

        # Most active hours
        cursor = conn.execute("""
            SELECT hour_of_day, COUNT(*) as count
            FROM ratings
            GROUP BY hour_of_day
            ORDER BY count DESC
            LIMIT 5
        """)
        active_hours = [
            {"hour": row["hour_of_day"], "count": row["count"]}
            for row in cursor.fetchall()
        ]

        # Most active days
        cursor = conn.execute("""
            SELECT day_of_week, COUNT(*) as count
            FROM ratings
            GROUP BY day_of_week
            ORDER BY count DESC
            LIMIT 7
        """)
        day_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]
        active_days = [
            {"day": day_names[row["day_of_week"]], "count": row["count"]}
            for row in cursor.fetchall()
        ]

        return {
            "total_tracks": total_tracks,
            "total_ratings": total_ratings,
            "rated_tracks": rated_tracks,
            "rating_distribution": rating_distribution,
            "active_hours": active_hours,
            "active_days": active_days,
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


def get_track_by_path(local_path: str) -> Optional[Dict[str, Any]]:
    """Get track information by file path."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM tracks
            WHERE local_path = ?
        """,
            (local_path,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_track_by_id(track_id: int) -> Optional[Dict[str, Any]]:
    """Get track information by ID."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM tracks WHERE id = ?
        """,
            (track_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_track_by_provider_id(provider: str, provider_id: str) -> Optional[Dict[str, Any]]:
    """Get track information by provider ID.

    Args:
        provider: Provider name ('soundcloud', 'spotify', 'youtube')
        provider_id: Provider-specific track ID

    Returns:
        Track dict or None if not found
    """
    column_map = {
        'soundcloud': 'soundcloud_id',
        'spotify': 'spotify_id',
        'youtube': 'youtube_id'
    }

    column = column_map.get(provider)
    if not column:
        return None

    with get_db_connection() as conn:
        cursor = conn.execute(
            f"""
            SELECT * FROM tracks WHERE {column} = ?
        """,
            (provider_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_track_path_to_id_map() -> Dict[str, int]:
    """Get mapping of file_path to track_id for all tracks in database.

    This is optimized for bulk lookups to avoid N+1 query problems.

    Returns:
        Dictionary mapping file paths to track IDs
    """
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT id, local_path FROM tracks")
        result = {}
        for row in cursor.fetchall():
            path = row["local_path"]
            if path:
                result[path] = row["id"]
        return result


def batch_upsert_tracks(tracks: List[Any]) -> Tuple[int, int]:
    """Batch insert or update tracks in database (optimized for large libraries).

    This function is 30-50x faster than individual get_or_create_track() calls
    by using a single query to check existing tracks and batch INSERT/UPDATE operations.

    Args:
        tracks: List of Track objects from domain.library.models

    Returns:
        Tuple of (added_count, updated_count)
    """
    if not tracks:
        return 0, 0

    # Get existing tracks in one query (avoids N+1 problem)
    existing_paths = get_track_path_to_id_map()

    # Separate new vs existing tracks
    new_tracks = []
    update_tracks = []

    for track in tracks:
        if track.local_path in existing_paths:
            update_tracks.append(
                (
                    track.title,
                    track.artist,
                    track.remix_artist,
                    track.album,
                    track.genre,
                    track.year,
                    track.duration,
                    track.key,  # key_signature
                    track.bpm,
                    existing_paths[track.local_path],  # id for WHERE clause
                )
            )
        else:
            new_tracks.append(
                (
                    track.local_path,  # local_path
                    track.title,
                    track.artist,
                    track.remix_artist,
                    track.album,
                    track.genre,
                    track.year,
                    track.duration,
                    track.key,  # key_signature
                    track.bpm,
                )
            )

    # Batch insert new tracks
    added = 0
    updated = 0

    with get_db_connection() as conn:
        if new_tracks:
            conn.executemany(
                """
                INSERT INTO tracks (local_path, title, artist, remix_artist, album, genre, year, duration, key_signature, bpm)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                new_tracks,
            )
            added = len(new_tracks)

        if update_tracks:
            conn.executemany(
                """
                UPDATE tracks SET
                    title = COALESCE(?, title),
                    artist = COALESCE(?, artist),
                    remix_artist = COALESCE(?, remix_artist),
                    album = COALESCE(?, album),
                    genre = COALESCE(?, genre),
                    year = COALESCE(?, year),
                    duration = COALESCE(?, duration),
                    key_signature = COALESCE(?, key_signature),
                    bpm = COALESCE(?, bpm),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                update_tracks,
            )
            updated = len(update_tracks)

        conn.commit()

    return added, updated


def update_ai_processed_note(note_id: int, ai_tags: str) -> None:
    """Mark a note as processed by AI and store extracted tags."""
    with get_db_connection() as conn:
        conn.execute(
            """
            UPDATE notes SET
                processed_by_ai = TRUE,
                ai_tags = ?
            WHERE id = ?
        """,
            (ai_tags, note_id),
        )
        conn.commit()


def get_unprocessed_notes() -> List[Dict[str, Any]]:
    """Get notes that haven't been processed by AI yet."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT n.id, n.note_text, n.timestamp,
                   t.title, t.artist,
                   t.local_path
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
            SELECT t.local_path
            FROM tracks t
            LEFT JOIN ratings r ON t.id = r.track_id AND r.rating_type = 'archive'
            WHERE r.id IS NULL
            ORDER BY t.artist, t.album, t.title
        """)
        return [row["local_path"] for row in cursor.fetchall()]


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


def get_all_tracks_with_metadata() -> List[Dict[str, Any]]:
    """Get all tracks with tags, notes, ratings, and play counts for search.

    Single optimized query with JOINs and aggregations for fast search pre-loading.

    Returns:
        List of track dicts with fields:
        - id, title, artist, remix_artist, album, year, genre, bpm, key_signature, file_path
        - tags: Comma-separated tag names (or empty string)
        - notes: Space-separated note texts (or empty string)
        - last_rating: Most recent rating type (or None)
        - play_count: Number of non-archive/skip ratings

    Performance:
        ~50-100ms for 5000 tracks with proper indexes
    """
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT
                t.id,
                t.title,
                t.artist,
                t.remix_artist,
                t.album,
                t.year,
                t.genre,
                t.bpm,
                t.key_signature,
                t.local_path,
                COALESCE(GROUP_CONCAT(DISTINCT tags.tag_name), '') as tags,
                COALESCE(GROUP_CONCAT(notes.note_text, ' '), '') as notes,
                (SELECT rating_type FROM ratings r
                 WHERE r.track_id = t.id
                 ORDER BY timestamp DESC LIMIT 1) as last_rating,
                (SELECT COUNT(*) FROM ratings r
                 WHERE r.track_id = t.id
                 AND r.rating_type NOT IN ('archive', 'skip')) as play_count
            FROM tracks t
            LEFT JOIN tags ON t.id = tags.track_id AND tags.blacklisted = FALSE
            LEFT JOIN notes ON t.id = notes.track_id
            GROUP BY t.id
            ORDER BY t.artist, t.title
        """)
        return [dict(row) for row in cursor.fetchall()]


def db_track_to_library_track(db_track: Dict[str, Any]):
    """Convert database track record to library.Track object."""
    # Import here to avoid circular imports
    from ..domain import library

    # Map database columns to Track fields
    # Ensure file_path is never None - use empty string for provider tracks without local files
    local_path = db_track.get("local_path") or ""

    # Log when converting NULL path to empty string (helps debug provider track issues)
    if not local_path and (
        db_track.get("soundcloud_id")
        or db_track.get("spotify_id")
        or db_track.get("youtube_id")
    ):
        logger.debug(
            f"Track {db_track.get('id')} has no local file path (provider track: "
            f"sc={bool(db_track.get('soundcloud_id'))}, "
            f"sp={bool(db_track.get('spotify_id'))}, "
            f"yt={bool(db_track.get('youtube_id'))})"
        )

    return library.Track(
        local_path=local_path,
        title=db_track.get("title"),
        artist=db_track.get("artist"),
        remix_artist=db_track.get("remix_artist"),
        album=db_track.get("album"),
        genre=db_track.get("genre"),
        year=db_track.get("year"),
        duration=db_track.get("duration"),
        bitrate=None,  # Not stored in database yet
        file_size=0,  # Not stored in database yet
        format=None,  # Could derive from local_path
        key=db_track.get("key_signature"),
        bpm=db_track.get("bpm"),
        soundcloud_id=db_track.get("soundcloud_id"),
        spotify_id=db_track.get("spotify_id"),
        youtube_id=db_track.get("youtube_id"),
    )


# Tag management functions


def add_tags(
    track_id: int,
    tags: List[str],
    source: str = "user",
    confidence: Optional[float] = None,
    reasoning: Optional[Dict[str, str]] = None,
) -> None:
    """Add multiple tags to a track.

    Args:
        track_id: ID of the track
        tags: List of tag names
        source: Source of tags ('user', 'ai', 'file')
        confidence: Optional confidence score
        reasoning: Optional dict mapping tag names to reasoning text (for AI tags)
    """
    with get_db_connection() as conn:
        for tag in tags:
            tag_name = tag.strip().lower()
            tag_reasoning = reasoning.get(tag_name) if reasoning else None
            conn.execute(
                """
                INSERT OR IGNORE INTO tags (track_id, tag_name, source, confidence, reasoning)
                VALUES (?, ?, ?, ?, ?)
            """,
                (track_id, tag_name, source, confidence, tag_reasoning),
            )
        conn.commit()


def get_track_tags(
    track_id: int, include_blacklisted: bool = False
) -> List[Dict[str, Any]]:
    """Get all tags for a track."""
    blacklist_filter = "" if include_blacklisted else "AND blacklisted = FALSE"

    with get_db_connection() as conn:
        cursor = conn.execute(
            f"""
            SELECT tag_name, source, confidence, created_at, blacklisted, reasoning
            FROM tags
            WHERE track_id = ? {blacklist_filter}
            ORDER BY created_at DESC
        """,
            (track_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def blacklist_tag(track_id: int, tag_name: str) -> bool:
    """Blacklist a tag for a specific track. Returns True if tag was found and blacklisted."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE tags SET blacklisted = TRUE
            WHERE track_id = ? AND tag_name = ? AND blacklisted = FALSE
        """,
            (track_id, tag_name.strip().lower()),
        )
        conn.commit()
        return cursor.rowcount > 0


def remove_tag(track_id: int, tag_name: str) -> bool:
    """Completely remove a tag from a track. Returns True if tag was found and removed."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            DELETE FROM tags
            WHERE track_id = ? AND tag_name = ?
        """,
            (track_id, tag_name.strip().lower()),
        )
        conn.commit()
        return cursor.rowcount > 0


# AI request logging functions


def log_ai_request(
    track_id: int,
    request_type: str,
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    response_time_ms: int,
    success: bool = True,
    error_message: Optional[str] = None,
) -> int:
    """Log an AI request and return the request ID."""
    total_tokens = prompt_tokens + completion_tokens

    # Hard-coded pricing for gpt-4o-mini (per 1M tokens)
    # Input: $0.15, Output: $0.60
    cost_estimate = (prompt_tokens * 0.15 / 1_000_000) + (
        completion_tokens * 0.60 / 1_000_000
    )

    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO ai_requests (
                track_id, request_type, model_name, prompt_tokens, 
                completion_tokens, total_tokens, cost_estimate,
                response_time_ms, success, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                track_id,
                request_type,
                model_name,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                cost_estimate,
                response_time_ms,
                success,
                error_message,
            ),
        )
        conn.commit()
        return cursor.lastrowid


def get_ai_usage_stats(days: Optional[int] = None) -> Dict[str, Any]:
    """Get AI usage statistics. If days is provided, filter to last N days."""
    date_filter = ""
    params = []

    if days:
        date_filter = "WHERE request_timestamp >= datetime('now', '-{} days')".format(
            days
        )

    with get_db_connection() as conn:
        # Total requests and tokens
        cursor = conn.execute(
            f"""
            SELECT 
                COUNT(*) as total_requests,
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(cost_estimate) as total_cost,
                AVG(response_time_ms) as avg_response_time,
                SUM(CASE WHEN success = TRUE THEN 1 ELSE 0 END) as successful_requests
            FROM ai_requests 
            {date_filter}
        """,
            params,
        )
        stats = dict(cursor.fetchone())

        # Request type breakdown
        cursor = conn.execute(
            f"""
            SELECT request_type, COUNT(*) as count, SUM(cost_estimate) as cost
            FROM ai_requests 
            {date_filter}
            GROUP BY request_type
        """,
            params,
        )
        request_types = {
            row["request_type"]: {"count": row["count"], "cost": row["cost"]}
            for row in cursor.fetchall()
        }

        # Daily breakdown if not filtering by days
        daily_stats = []
        if not days or days > 1:
            cursor = conn.execute(
                f"""
                SELECT 
                    DATE(request_timestamp) as date,
                    COUNT(*) as requests,
                    SUM(cost_estimate) as cost
                FROM ai_requests 
                {date_filter}
                GROUP BY DATE(request_timestamp)
                ORDER BY date DESC
                LIMIT 30
            """,
                params,
            )
            daily_stats = [dict(row) for row in cursor.fetchall()]

        stats["request_types"] = request_types
        stats["daily_breakdown"] = daily_stats

        # Convert None values to 0 for display
        for key in [
            "total_prompt_tokens",
            "total_completion_tokens",
            "total_tokens",
            "total_cost",
        ]:
            if stats[key] is None:
                stats[key] = 0

        return stats


def get_tracks_needing_analysis() -> List[Dict[str, Any]]:
    """Get tracks that need AI analysis (have notes but no AI tags)."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT DISTINCT t.*
            FROM tracks t
            INNER JOIN notes n ON t.id = n.track_id
            LEFT JOIN tags tag ON t.id = tag.track_id AND tag.source = 'ai'
            LEFT JOIN ratings r ON t.id = r.track_id AND r.rating_type = 'archive'
            WHERE tag.id IS NULL
            AND r.id IS NULL
            ORDER BY n.timestamp DESC
        """)
        return [dict(row) for row in cursor.fetchall()]


# Provider State Functions


def save_provider_state(
    provider: str, auth_data: Dict[str, Any], config: Dict[str, Any]
) -> None:
    """Save provider authentication state to database.

    Args:
        provider: Provider name ('soundcloud', 'spotify', etc.)
        auth_data: Authentication data (tokens, expiry)
        config: Provider configuration
    """
    import json

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO provider_state (provider, authenticated, auth_data, config, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
            (provider, True, json.dumps(auth_data), json.dumps(config)),
        )
        conn.commit()


def load_provider_state(provider: str) -> Optional[Dict[str, Any]]:
    """Load provider authentication state from database.

    Args:
        provider: Provider name

    Returns:
        {'authenticated': bool, 'auth_data': dict, 'config': dict} or None
    """
    import json

    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT authenticated, auth_data, config
            FROM provider_state
            WHERE provider = ?
        """,
            (provider,),
        )

        row = cursor.fetchone()
        if not row:
            return None

        return {
            "authenticated": bool(row["authenticated"]),
            "auth_data": json.loads(row["auth_data"]) if row["auth_data"] else {},
            "config": json.loads(row["config"]) if row["config"] else {},
        }


# Metadata Editor Functions


def update_track_metadata(track_id: int, **fields) -> bool:
    """Update track metadata fields.

    Args:
        track_id: Track ID to update
        **fields: Field name/value pairs (title, artist, remix_artist, album, year, bpm, key_signature, genre)

    Returns:
        True if successful
    """
    if not fields:
        return False

    # Validate field names
    valid_fields = {
        "title",
        "artist",
        "remix_artist",
        "album",
        "year",
        "bpm",
        "key_signature",
        "genre",
    }
    invalid_fields = set(fields.keys()) - valid_fields
    if invalid_fields:
        raise ValueError(f"Invalid fields: {invalid_fields}")

    # Validate field values
    validated_fields = {}
    for field, value in fields.items():
        # Skip None values (allow clearing fields)
        if value is None or value == "":
            validated_fields[field] = None
            continue

        # Type-specific validation
        if field == "year":
            try:
                year_val = int(value)
                if not (1900 <= year_val <= 2100):
                    raise ValueError(
                        f"Year must be between 1900 and 2100, got {year_val}"
                    )
                validated_fields[field] = year_val
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid year value '{value}': {e}")

        elif field == "bpm":
            try:
                bpm_val = int(value)
                if not (1 <= bpm_val <= 300):
                    raise ValueError(f"BPM must be between 1 and 300, got {bpm_val}")
                validated_fields[field] = bpm_val
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid BPM value '{value}': {e}")

        elif field in (
            "title",
            "artist",
            "remix_artist",
            "album",
            "genre",
            "key_signature",
        ):
            # String fields: just convert to string and trim
            validated_fields[field] = str(value).strip()

    # Build UPDATE query dynamically
    set_clause = ", ".join(f"{field} = ?" for field in validated_fields.keys())
    values = list(validated_fields.values()) + [track_id]

    with get_db_connection() as conn:
        conn.execute(
            f"""
            UPDATE tracks
            SET {set_clause}
            WHERE id = ?
        """,
            values,
        )
        conn.commit()

    return True


def delete_rating(track_id: int, rating_timestamp: str) -> bool:
    """Delete specific rating by timestamp.

    Args:
        track_id: Track ID
        rating_timestamp: ISO format timestamp

    Returns:
        True if rating was deleted
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            DELETE FROM ratings
            WHERE track_id = ? AND timestamp = ?
        """,
            (track_id, rating_timestamp),
        )
        conn.commit()
        return cursor.rowcount > 0


def update_rating(track_id: int, old_timestamp: str, new_rating_type: str) -> bool:
    """Update rating type for a specific rating.

    Args:
        track_id: Track ID
        old_timestamp: Original timestamp of rating
        new_rating_type: New rating type (archive, like, love)

    Returns:
        True if rating was updated
    """
    # Validate rating type
    valid_types = {"archive", "like", "love"}
    if new_rating_type not in valid_types:
        raise ValueError(f"Invalid rating type. Must be one of: {valid_types}")

    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE ratings
            SET rating_type = ?
            WHERE track_id = ? AND timestamp = ?
        """,
            (new_rating_type, track_id, old_timestamp),
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_note(track_id: int, note_timestamp: str) -> bool:
    """Delete specific note by timestamp.

    Args:
        track_id: Track ID
        note_timestamp: ISO format timestamp

    Returns:
        True if note was deleted
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            DELETE FROM notes
            WHERE track_id = ? AND timestamp = ?
        """,
            (track_id, note_timestamp),
        )
        conn.commit()
        return cursor.rowcount > 0


def update_note(track_id: int, old_timestamp: str, new_note_text: str) -> bool:
    """Update note text for a specific note.

    Args:
        track_id: Track ID
        old_timestamp: Original timestamp of note
        new_note_text: New note text

    Returns:
        True if note was updated
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE notes
            SET note_text = ?
            WHERE track_id = ? AND timestamp = ?
        """,
            (new_note_text, track_id, old_timestamp),
        )
        conn.commit()
        return cursor.rowcount > 0
