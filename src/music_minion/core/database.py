"""
SQLite database operations for Music Minion CLI
"""

import sqlite3
import unicodedata
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import emoji
from loguru import logger

from .config import get_data_dir
from ..domain.library.models import Track


# Database schema version for migrations
SCHEMA_VERSION = 35  # Add player_queue_state table


# Initial top 50 curated emojis for music reactions
INITIAL_TOP_50_EMOJIS = [
    # Energy/Vibe (8)
    ("🔥", "fire"), ("⚡", "high voltage"), ("💥", "collision"),
    ("✨", "sparkles"), ("🌟", "star"), ("💫", "dizzy"),
    ("🎆", "fireworks"), ("🌈", "rainbow"),

    # Emotions (10)
    ("💪", "flexed biceps"), ("🎯", "direct hit"), ("😍", "smiling face with heart-eyes"),
    ("😎", "smiling face with sunglasses"), ("🤘", "sign of the horns"),
    ("👌", "ok hand"), ("🙌", "raising hands"), ("💖", "sparkling heart"),
    ("❤️", "red heart"), ("💯", "hundred points"),

    # Music/Audio (8)
    ("🎵", "musical note"), ("🎶", "musical notes"), ("🎤", "microphone"),
    ("🎧", "headphone"), ("🔊", "speaker high volume"), ("🎸", "guitar"),
    ("🎹", "musical keyboard"), ("🥁", "drum"),

    # Dance/Movement (6)
    ("💃", "woman dancing"), ("🕺", "man dancing"), ("🪩", "mirror ball"),
    ("🎉", "party popper"), ("🎊", "confetti ball"), ("🏃", "person running"),

    # Chill/Relaxed (6)
    ("😌", "relieved face"), ("🌙", "crescent moon"), ("☁️", "cloud"),
    ("🌊", "water wave"), ("🍃", "leaf fluttering in wind"), ("🧘", "person in lotus position"),

    # Miscellaneous (12)
    ("🚀", "rocket"), ("💎", "gem stone"), ("👑", "crown"),
    ("🌺", "hibiscus"), ("🔮", "crystal ball"), ("⭐", "star"),
    ("🌸", "cherry blossom"), ("🦋", "butterfly"), ("🐉", "dragon"),
    ("🎭", "performing arts"), ("🏆", "trophy"), ("🎨", "artist palette")
]


def normalize_emoji_id(emoji_str: str) -> str:
    """Normalize emoji ID to consistent form.

    For Unicode emojis: Normalizes to NFC form, strips variation selectors.
    For custom emojis (UUIDs): Returns unchanged.

    Args:
        emoji_str: Either Unicode emoji character or UUID for custom emoji

    Returns:
        Normalized emoji identifier
    """
    # UUID pattern check for custom emojis (they don't need normalization)
    if len(emoji_str) == 36 and emoji_str.count('-') == 4:
        return emoji_str

    # Strip variation selectors (VS15 text, VS16 emoji presentation)
    emoji_str = emoji_str.replace('\ufe0e', '').replace('\ufe0f', '')

    # Normalize Unicode emojis to NFC form
    return unicodedata.normalize('NFC', emoji_str)


def seed_initial_emojis(conn) -> None:
    """Seed emoji_metadata with curated top 50 music-relevant emojis."""
    conn.executemany(
        """
        INSERT OR IGNORE INTO emoji_metadata (emoji_id, default_name, use_count)
        VALUES (?, ?, 0)
        """,
        INITIAL_TOP_50_EMOJIS
    )
    conn.commit()

    # Verify FTS index was populated by triggers
    cursor = conn.execute("SELECT COUNT(*) FROM emoji_metadata_fts")
    fts_count = cursor.fetchone()[0]
    if fts_count != 50:
        logger.error(f"FTS index not properly populated. Expected 50, got {fts_count}")
        logger.info("Run this to rebuild: INSERT INTO emoji_metadata_fts SELECT rowid, emoji_id, custom_name, default_name FROM emoji_metadata")


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


def get_active_provider() -> str:
    """Get the currently active library provider.

    Returns:
        Provider name: 'local', 'soundcloud', 'spotify', 'youtube', or 'all'
    """
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT provider FROM active_library WHERE id = 1")
        row = cursor.fetchone()
        return row["provider"] if row else "local"


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

    if current_version < 14:
        # Migration from v13 to v14: Remove file_path column
        print("  Migrating to v14: Removing file_path column...")

        # Commit any pending operations
        conn.commit()

        # Step 1: Disable foreign keys during table recreation
        conn.execute("PRAGMA foreign_keys=OFF")

        # Step 2: Create new tracks table without file_path column
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

        # Step 3: Copy all data from old table
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

        # Step 4: Drop old table
        conn.execute("DROP TABLE tracks")

        # Step 5: Rename new table
        conn.execute("ALTER TABLE tracks_new RENAME TO tracks")

        # Step 6: Recreate all indexes
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

        # Step 7: Re-enable foreign keys
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
            conn.execute(
                "ALTER TABLE playlists ADD COLUMN provider_last_modified TIMESTAMP"
            )
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        print("  ✓ Migration to v15 complete: Playlist sync timestamps added")
        conn.commit()

    if current_version < 16:
        # Migration from v15 to v16: Add provider_created_at for sorting playlists by creation date

        # Add provider_created_at column to track when playlists were created on the provider (e.g., SoundCloud)
        try:
            conn.execute(
                "ALTER TABLE playlists ADD COLUMN provider_created_at TIMESTAMP"
            )
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

    if current_version < 18:
        # Migration from v17 to v18: Add snapshot_id for Spotify playlist change detection
        print("  Migrating to v18: Adding spotify_snapshot_id column...")

        try:
            conn.execute("ALTER TABLE playlists ADD COLUMN spotify_snapshot_id TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        print("  ✓ Migration to v18 complete: Spotify snapshot_id column added")
        conn.commit()

    if current_version < 19:
        # Migration from v18 to v19: Library-specific playlists
        print("  Migrating to v19: Adding library-specific playlists...")

        # 1. Add library column to playlists table
        try:
            conn.execute(
                "ALTER TABLE playlists ADD COLUMN library TEXT DEFAULT 'local'"
            )
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # 2. Set library based on provider IDs (smart migration)
        # SoundCloud playlists
        conn.execute("""
            UPDATE playlists
            SET library = 'soundcloud'
            WHERE soundcloud_playlist_id IS NOT NULL
        """)

        # Spotify playlists
        conn.execute("""
            UPDATE playlists
            SET library = 'spotify'
            WHERE spotify_playlist_id IS NOT NULL
        """)

        # YouTube playlists (if any exist in future)
        conn.execute("""
            UPDATE playlists
            SET library = 'youtube'
            WHERE youtube_playlist_id IS NOT NULL
        """)

        # Local playlists (no provider ID)
        conn.execute("""
            UPDATE playlists
            SET library = 'local'
            WHERE library IS NULL
        """)

        # 3. Create index on library column for fast filtering
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_playlists_library ON playlists (library)"
        )

        # 4. Recreate active_playlist table to support per-library active playlists
        # First, save the existing active playlist data
        cursor = conn.execute(
            "SELECT playlist_id, last_played_track_id, last_played_position, last_played_at, activated_at FROM active_playlist WHERE id = 1"
        )
        existing_data = cursor.fetchone()

        # Drop the old singleton table
        conn.execute("DROP TABLE IF EXISTS active_playlist")

        # Create new active_playlist table with library column
        conn.execute("""
            CREATE TABLE active_playlist (
                library TEXT PRIMARY KEY,
                playlist_id INTEGER,
                last_played_track_id INTEGER,
                last_played_position INTEGER,
                last_played_at TIMESTAMP,
                activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE SET NULL
            )
        """)

        # Restore existing active playlist data for 'local' library
        if existing_data and existing_data["playlist_id"]:
            conn.execute(
                """
                INSERT INTO active_playlist (library, playlist_id, last_played_track_id, last_played_position, last_played_at, activated_at)
                VALUES ('local', ?, ?, ?, ?, ?)
            """,
                (
                    existing_data["playlist_id"],
                    existing_data["last_played_track_id"],
                    existing_data["last_played_position"],
                    existing_data["last_played_at"],
                    existing_data["activated_at"],
                ),
            )

        print("  ✓ Migration to v19 complete: Library-specific playlists added")
        conn.commit()

    if current_version < 20:
        # Migration from v19 to v20: Add top_level_artist column for better matching
        print("  Migrating to v20: Adding top_level_artist column...")

        try:
            conn.execute("ALTER TABLE tracks ADD COLUMN top_level_artist TEXT")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # Populate top_level_artist for existing tracks (extract first artist from artist field)
        conn.execute("""
            UPDATE tracks
            SET top_level_artist = CASE
                WHEN artist LIKE '%,%' THEN SUBSTR(artist, 1, INSTR(artist, ',') - 1)
                ELSE artist
            END
            WHERE top_level_artist IS NULL AND artist IS NOT NULL
        """)

        print("  ✓ Migration to v20 complete: top_level_artist column added")
        conn.commit()

    if current_version < 21:
        # Migration from v20 to v21: Add Elo rating system
        logger.info("Migrating database to schema version 21 (Elo ratings)...")

        # Create elo_ratings table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS elo_ratings (
                track_id INTEGER PRIMARY KEY,
                rating REAL DEFAULT 1500.0,
                comparison_count INTEGER DEFAULT 0,
                last_compared TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE
            )
        """)

        # Create comparison_history table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS comparison_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_a_id INTEGER NOT NULL,
                track_b_id INTEGER NOT NULL,
                winner_id INTEGER NOT NULL,
                track_a_rating_before REAL NOT NULL,
                track_b_rating_before REAL NOT NULL,
                track_a_rating_after REAL NOT NULL,
                track_b_rating_after REAL NOT NULL,
                session_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (track_a_id) REFERENCES tracks (id) ON DELETE CASCADE,
                FOREIGN KEY (track_b_id) REFERENCES tracks (id) ON DELETE CASCADE,
                FOREIGN KEY (winner_id) REFERENCES tracks (id) ON DELETE CASCADE
            )
        """)

        # Create indexes for performance
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_elo_rating ON elo_ratings(rating DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_elo_comparison_count ON elo_ratings(comparison_count)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_comparison_session ON comparison_history(session_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_comparison_timestamp ON comparison_history(timestamp DESC)"
        )

        # Initialize ratings for all existing tracks
        conn.execute("""
            INSERT INTO elo_ratings (track_id, rating, comparison_count)
            SELECT id, 1500.0, 0
            FROM tracks
            WHERE id NOT IN (SELECT track_id FROM elo_ratings)
        """)

        logger.info("Migration to schema version 21 complete")
        conn.commit()

    if current_version < 22:
        # Migration from v21 to v22: Add playlist builder state table
        logger.info(
            "Migrating database to schema version 22 (playlist builder state)..."
        )

        # Create playlist_builder_state table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS playlist_builder_state (
                playlist_id INTEGER PRIMARY KEY,
                scroll_position INTEGER DEFAULT 0,
                sort_field TEXT DEFAULT 'artist',
                sort_direction TEXT DEFAULT 'asc',
                active_filters TEXT DEFAULT '[]',
                last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE
            )
        """)

        logger.info("Migration to schema version 22 complete")
        conn.commit()

    if current_version < 23:
        # Migration from v22 to v23: Add metadata change tracking
        logger.info(
            "Migrating database to schema version 23 (metadata change tracking)..."
        )

        # Add metadata_updated_at column to tracks table
        try:
            conn.execute("ALTER TABLE tracks ADD COLUMN metadata_updated_at TIMESTAMP")
        except sqlite3.OperationalError:
            pass  # Column already exists

        logger.info("Migration to schema version 23 complete")
        conn.commit()

    if current_version < 24:
        # Migration from v23 to v24: Add playback session tracking table
        logger.info(
            "Migrating database to schema version 24 (playback session tracking)..."
        )

        # Create track_listen_sessions table for detailed listening analytics
        conn.execute("""
            CREATE TABLE IF NOT EXISTS track_listen_sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                play_date DATE NOT NULL,
                playlist_id INTEGER NULL,
                seconds_played REAL NOT NULL DEFAULT 0,
                FOREIGN KEY (track_id) REFERENCES tracks(id)
            )
        """)

        # Create indexes for performance
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_track ON track_listen_sessions(track_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_date ON track_listen_sessions(play_date)"
        )

        logger.info("Migration to schema version 24 complete")
        conn.commit()

    if current_version < 25:
        # Migration from v24 to v25: Add wins tracking to elo_ratings
        logger.info("Migrating database to schema version 25 (Elo wins tracking)...")

        # Add wins column
        try:
            conn.execute("ALTER TABLE elo_ratings ADD COLUMN wins INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists

        # Backfill wins from comparison_history
        logger.info("Backfilling wins from comparison history...")
        conn.execute("""
            UPDATE elo_ratings
            SET wins = (
                SELECT COUNT(*)
                FROM comparison_history
                WHERE winner_id = elo_ratings.track_id
            )
        """)

        logger.info("Migration to schema version 25 complete")
        conn.commit()

    if current_version < 26:
        # Migration from v25 to v26: Add playlist-specific ELO rating system
        logger.info("Migrating database to schema version 26 (Playlist ELO ratings)...")

        # Playlist-specific ELO ratings table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS playlist_elo_ratings (
                track_id TEXT NOT NULL,
                playlist_id INTEGER NOT NULL,
                rating REAL DEFAULT 1500.0,
                comparison_count INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                last_compared TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (track_id, playlist_id),
                FOREIGN KEY (track_id) REFERENCES tracks(id),
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
            )
        """)

        # Playlist comparison history table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS playlist_comparison_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_a_id TEXT NOT NULL,
                track_b_id TEXT NOT NULL,
                winner_id TEXT NOT NULL,
                playlist_id INTEGER NOT NULL,
                affects_global BOOLEAN NOT NULL,
                track_a_playlist_rating_before REAL,
                track_a_playlist_rating_after REAL,
                track_b_playlist_rating_before REAL,
                track_b_playlist_rating_after REAL,
                track_a_global_rating_before REAL,
                track_a_global_rating_after REAL,
                track_b_global_rating_before REAL,
                track_b_global_rating_after REAL,
                session_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (track_a_id) REFERENCES tracks(id),
                FOREIGN KEY (track_b_id) REFERENCES tracks(id),
                FOREIGN KEY (winner_id) REFERENCES tracks(id),
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
            )
        """)

        # Session tracking for resumable playlist ranking
        conn.execute("""
            CREATE TABLE IF NOT EXISTS playlist_ranking_sessions (
                playlist_id INTEGER PRIMARY KEY,
                session_id TEXT NOT NULL,
                last_track_a_id TEXT,
                last_track_b_id TEXT,
                progress_stats TEXT, -- JSON: {"compared": 45, "total": 120}
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE
            )
        """)

        # Create indexes for performance
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_playlist_elo_ratings_playlist_id
            ON playlist_elo_ratings(playlist_id, rating DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_playlist_comparison_history_playlist_id
            ON playlist_comparison_history(playlist_id, timestamp DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_playlist_ranking_sessions_playlist_id
            ON playlist_ranking_sessions(playlist_id)
        """)

        logger.info("Migration to schema version 26 complete")
        conn.commit()

    if current_version < 27:
        # Migration from v26 to v27: Add playlist builder tables
        logger.info("Migrating database to schema version 27 (Playlist Builder)...")

        # Playlist builder filters (separate from smart playlist filters)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS playlist_builder_filters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL,
                field TEXT NOT NULL,
                operator TEXT NOT NULL,
                value TEXT NOT NULL,
                conjunction TEXT NOT NULL DEFAULT 'AND',
                FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_builder_filters_playlist
            ON playlist_builder_filters(playlist_id)
        """)

        # Permanently skipped tracks per playlist
        conn.execute("""
            CREATE TABLE IF NOT EXISTS playlist_builder_skipped (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL,
                track_id INTEGER NOT NULL,
                skipped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE,
                FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE,
                UNIQUE (playlist_id, track_id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_builder_skipped_playlist
            ON playlist_builder_skipped(playlist_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_builder_skipped_track
            ON playlist_builder_skipped(track_id)
        """)

        # Active builder sessions
        conn.execute("""
            CREATE TABLE IF NOT EXISTS playlist_builder_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER UNIQUE NOT NULL,
                last_processed_track_id INTEGER,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE,
                FOREIGN KEY (last_processed_track_id) REFERENCES tracks (id) ON DELETE SET NULL
            )
        """)

        logger.info("Migration to schema version 27 complete")
        conn.commit()

    if current_version < 28:
        # Migration from v27 to v28: Add personal radio station tables
        logger.info("Migrating database to schema version 28 (Personal Radio)...")

        # Stations table - links to existing playlists with radio-specific metadata
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                playlist_id INTEGER REFERENCES playlists(id) ON DELETE SET NULL,
                mode TEXT NOT NULL DEFAULT 'shuffle',  -- 'shuffle' | 'queue'
                is_active BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Station schedule - time ranges for meta-stations (like Main)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS station_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
                start_time TEXT NOT NULL,  -- "06:00" format
                end_time TEXT NOT NULL,    -- "09:00" format
                target_station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
                position INTEGER DEFAULT 0,  -- Order for overlapping ranges
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Radio playback history
        conn.execute("""
            CREATE TABLE IF NOT EXISTS radio_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_id INTEGER REFERENCES stations(id) ON DELETE SET NULL,
                track_id INTEGER REFERENCES tracks(id) ON DELETE SET NULL,
                source_type TEXT NOT NULL,  -- 'local' | 'youtube' | 'spotify' | 'soundcloud'
                source_url TEXT,            -- For non-local sources
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ended_at TIMESTAMP,
                position_ms INTEGER DEFAULT 0  -- Where in track we started
            )
        """)

        # Radio state for resume after restart
        conn.execute("""
            CREATE TABLE IF NOT EXISTS radio_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                active_station_id INTEGER REFERENCES stations(id) ON DELETE SET NULL,
                started_at TIMESTAMP,
                last_track_id INTEGER REFERENCES tracks(id) ON DELETE SET NULL,
                last_position_ms INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Initialize radio state with no active station
        conn.execute("""
            INSERT OR IGNORE INTO radio_state (id, active_station_id, last_position_ms)
            VALUES (1, NULL, 0)
        """)

        # Session-level skipped tracks (cleared daily with shuffle reseed)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS radio_skipped (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
                track_id INTEGER REFERENCES tracks(id) ON DELETE CASCADE,
                source_url TEXT,
                skipped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                skip_date DATE DEFAULT (DATE('now')),  -- For daily clearing
                reason TEXT  -- 'unavailable' | 'error'
            )
        """)

        # Create indexes for performance
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_station_schedule_station ON station_schedule(station_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_station_schedule_target ON station_schedule(target_station_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_radio_history_station ON radio_history(station_id, started_at DESC)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_radio_history_track ON radio_history(track_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_radio_skipped_station_date ON radio_skipped(station_id, skip_date)"
        )

        logger.info("Migration to schema version 28 complete")
        conn.commit()

    if current_version < 29:
        # Migration from v28 to v29: Add source_url for streaming tracks
        logger.info("Migrating database to schema version 29 (SoundCloud streaming)...")

        # Add source_url column to tracks table for streaming permalink URLs
        try:
            conn.execute("""
                ALTER TABLE tracks ADD COLUMN source_url TEXT
            """)
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # Index for source_url lookups (partial index, only non-null values)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tracks_source_url
            ON tracks(source_url) WHERE source_url IS NOT NULL
        """)

        logger.info("Migration to schema version 29 complete")
        conn.commit()

    if current_version < 30:
        # Migration from v29 to v30: Add source_filter to stations
        logger.info("Migrating database to schema version 30 (Station Source Filter)...")

        try:
            conn.execute(
                "ALTER TABLE stations ADD COLUMN source_filter TEXT NOT NULL DEFAULT 'all'"
            )
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        # Auto-migrate existing YouTube stations
        conn.execute("""
            UPDATE stations
            SET source_filter = 'youtube'
            WHERE name LIKE '%YouTube%' OR name LIKE '%youtube%'
        """)

        logger.info("Migration to schema version 30 complete")
        conn.commit()

    if current_version < 31:
        logger.info("Migrating to v31: Adding emoji reaction tables")

        # Track-emoji associations (many-to-many)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS track_emojis (
                track_id INTEGER NOT NULL,
                emoji_id TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (track_id, emoji_id),
                FOREIGN KEY (track_id) REFERENCES tracks (id) ON DELETE CASCADE
            )
        """)

        # Emoji metadata (usage stats + custom names + custom emoji support)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS emoji_metadata (
                emoji_id TEXT PRIMARY KEY,
                type TEXT NOT NULL DEFAULT 'unicode',
                file_path TEXT,
                custom_name TEXT,
                default_name TEXT NOT NULL,
                use_count INTEGER DEFAULT 0,
                last_used TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create custom_emojis directory for uploaded images
        custom_emojis_dir = get_data_dir() / "custom_emojis"
        custom_emojis_dir.mkdir(exist_ok=True)

        # Performance indexes
        conn.execute("CREATE INDEX idx_track_emojis_track_id ON track_emojis(track_id)")
        conn.execute("CREATE INDEX idx_track_emojis_emoji_id ON track_emojis(emoji_id)")  # For emoji filtering

        # Regular indexes for sorting
        conn.execute("CREATE INDEX idx_emoji_metadata_use_count ON emoji_metadata(use_count DESC, last_used DESC)")

        # Full-Text Search index for searching emoji names (supports ALL emojis, not just initial 50)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS emoji_metadata_fts USING fts5(
                emoji_id UNINDEXED,
                custom_name,
                default_name,
                content=emoji_metadata,
                content_rowid=rowid
            )
        """)

        # Triggers to keep FTS index in sync with emoji_metadata
        conn.execute("""
            CREATE TRIGGER emoji_metadata_fts_insert AFTER INSERT ON emoji_metadata BEGIN
                INSERT INTO emoji_metadata_fts(rowid, emoji_id, custom_name, default_name)
                VALUES (new.rowid, new.emoji_id, new.custom_name, new.default_name);
            END
        """)

        conn.execute("""
            CREATE TRIGGER emoji_metadata_fts_update AFTER UPDATE ON emoji_metadata BEGIN
                UPDATE emoji_metadata_fts
                SET custom_name = new.custom_name, default_name = new.default_name
                WHERE rowid = new.rowid;
            END
        """)

        conn.execute("""
            CREATE TRIGGER emoji_metadata_fts_delete AFTER DELETE ON emoji_metadata BEGIN
                DELETE FROM emoji_metadata_fts WHERE rowid = old.rowid;
            END
        """)

        conn.commit()

        # Seed initial 50 emojis
        seed_initial_emojis(conn)

        logger.info("Migration to schema version 31 complete")

    if current_version < 32:
        # Migration from v31 to v32: Playlist pinning
        print("  Migrating to v32: Adding playlist pinning support...")

        try:
            conn.execute("ALTER TABLE playlists ADD COLUMN pin_order INTEGER DEFAULT NULL")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                raise

        conn.execute("CREATE INDEX IF NOT EXISTS idx_playlists_pin_order ON playlists(pin_order)")

        print("  ✓ Migration to v32 complete: Playlist pinning support added")
        conn.commit()

    if current_version < 33:
        # Migration from v32 to v33: Consolidate global ELO to "All" playlist
        print("  Migrating to v33: Consolidating ELO rankings to playlist-based system...")

        # Add performance indexes first
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_playlist_comparison_track_a
            ON playlist_comparison_history(playlist_id, track_a_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_playlist_comparison_track_b
            ON playlist_comparison_history(playlist_id, track_b_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_playlist_elo_comparison_count
            ON playlist_elo_ratings(playlist_id, comparison_count)
        """)

        # Find "All" playlist ID
        cursor = conn.execute("SELECT id FROM playlists WHERE name = 'All' LIMIT 1")
        all_playlist = cursor.fetchone()

        if all_playlist:
            all_id = all_playlist['id']

            # Count data before migration
            cursor = conn.execute("SELECT COUNT(*) FROM elo_ratings")
            old_ratings = cursor.fetchone()[0]

            cursor = conn.execute("SELECT COUNT(*) FROM comparison_history")
            old_comparisons = cursor.fetchone()[0]

            # Migrate global ELO ratings to "All" playlist
            conn.execute("""
                INSERT OR REPLACE INTO playlist_elo_ratings (track_id, playlist_id, rating, comparison_count, wins)
                SELECT
                    er.track_id,
                    ? as playlist_id,
                    er.rating,
                    er.comparison_count,
                    er.wins
                FROM elo_ratings er
            """, (all_id,))

            # Migrate global comparison history to "All" playlist
            # Map old global ratings to both playlist and global columns
            conn.execute("""
                INSERT INTO playlist_comparison_history (
                    playlist_id, track_a_id, track_b_id, winner_id, affects_global,
                    track_a_playlist_rating_before, track_a_playlist_rating_after,
                    track_b_playlist_rating_before, track_b_playlist_rating_after,
                    track_a_global_rating_before, track_a_global_rating_after,
                    track_b_global_rating_before, track_b_global_rating_after,
                    session_id, timestamp
                )
                SELECT
                    ? as playlist_id,
                    ch.track_a_id, ch.track_b_id, ch.winner_id,
                    1 as affects_global,
                    ch.track_a_rating_before, ch.track_a_rating_after,
                    ch.track_b_rating_before, ch.track_b_rating_after,
                    ch.track_a_rating_before, ch.track_a_rating_after,
                    ch.track_b_rating_before, ch.track_b_rating_after,
                    ch.session_id, ch.timestamp
                FROM comparison_history ch
            """, (all_id,))

            # Count data after migration
            cursor = conn.execute(
                "SELECT COUNT(*) FROM playlist_elo_ratings WHERE playlist_id = ?",
                (all_id,)
            )
            new_ratings = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT COUNT(*) FROM playlist_comparison_history WHERE playlist_id = ?",
                (all_id,)
            )
            new_comparisons = cursor.fetchone()[0]

            # Log migration results
            logger.info("✅ Migration to v33 complete:")
            logger.info(f"  - Ratings: {new_ratings} / {old_ratings} migrated to All playlist")
            logger.info(f"  - Comparisons: {new_comparisons} / {old_comparisons} migrated to All playlist")

            if new_ratings != old_ratings or new_comparisons != old_comparisons:
                logger.warning("⚠️  Migration mismatch detected - check for data issues")

        # Backup old tables (can be removed in future migration if all is well)
        try:
            conn.execute("ALTER TABLE comparison_history RENAME TO _backup_comparison_history")
        except sqlite3.OperationalError as e:
            if "no such table" not in str(e).lower() and "already exists" not in str(e).lower():
                raise

        try:
            conn.execute("ALTER TABLE elo_ratings RENAME TO _backup_elo_ratings")
        except sqlite3.OperationalError as e:
            if "no such table" not in str(e).lower() and "already exists" not in str(e).lower():
                raise

        try:
            conn.execute("ALTER TABLE playlist_ranking_sessions RENAME TO _backup_playlist_ranking_sessions")
        except sqlite3.OperationalError as e:
            if "no such table" not in str(e).lower() and "already exists" not in str(e).lower():
                raise

        print("  ✓ Migration to v33 complete: ELO rankings consolidated to playlist-based system")
        conn.commit()

    if current_version < 34:
        print("  Migrating to v34: Materializing smart playlists...")

        # Get all smart playlists
        cursor = conn.execute("SELECT id, name FROM playlists WHERE type = 'smart'")
        smart_playlists = cursor.fetchall()

        for playlist in smart_playlists:
            playlist_id = playlist["id"]
            playlist_name = playlist["name"]

            try:
                # Get filters for this playlist
                cursor = conn.execute(
                    "SELECT field, operator, value, conjunction FROM playlist_filters WHERE playlist_id = ? ORDER BY id",
                    (playlist_id,)
                )
                filters = cursor.fetchall()

                if not filters:
                    # No filters = no tracks
                    print(f"    Skipping '{playlist_name}' (no filters)")
                    continue

                # Build WHERE clause (simplified - handles common cases)
                # For complex filters, may need to run refresh after migration
                where_parts = []
                params = []
                for f in filters:
                    field, operator, value = f["field"], f["operator"], f["value"]

                    # Map field to column (key -> key_signature)
                    column = "key_signature" if field == "key" else field

                    # Skip emoji filters in migration (complex subquery)
                    if field == "emoji":
                        continue

                    if operator == "contains":
                        where_parts.append(f"{column} LIKE ?")
                        params.append(f"%{value}%")
                    elif operator == "equals":
                        where_parts.append(f"{column} = ?")
                        params.append(value)
                    elif operator == "gte":
                        where_parts.append(f"{column} >= ?")
                        params.append(value)
                    elif operator == "lte":
                        where_parts.append(f"{column} <= ?")
                        params.append(value)
                    # Add other operators as needed

                if not where_parts:
                    print(f"    Skipping '{playlist_name}' (unsupported filters)")
                    continue

                where_clause = " AND ".join(where_parts)

                # Clear existing playlist_tracks
                conn.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))

                # Insert matching tracks
                cursor = conn.execute(
                    f"""
                    SELECT id FROM tracks t
                    WHERE {where_clause}
                    AND t.id NOT IN (SELECT track_id FROM playlist_builder_skipped WHERE playlist_id = ?)
                    ORDER BY artist, album, title
                    """,
                    tuple(params) + (playlist_id,)
                )
                track_ids = [row["id"] for row in cursor.fetchall()]

                # Batch insert
                conn.executemany(
                    "INSERT INTO playlist_tracks (playlist_id, track_id, position, added_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                    [(playlist_id, tid, pos) for pos, tid in enumerate(track_ids)]
                )

                # Update track_count
                conn.execute(
                    "UPDATE playlists SET track_count = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (len(track_ids), playlist_id)
                )

                print(f"    Materialized '{playlist_name}': {len(track_ids)} tracks")

            except Exception as e:
                print(f"    Warning: Failed to materialize '{playlist_name}': {e}")

        print("  ✓ Migration to v34 complete: Smart playlists materialized")
        conn.commit()

    if current_version < 35:
        logger.info("Migrating to v35: Add player_queue_state table")
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS player_queue_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    context_type TEXT NOT NULL,
                    context_id INTEGER,
                    shuffle_enabled BOOLEAN NOT NULL,
                    sort_field TEXT,
                    sort_direction TEXT,
                    queue_track_ids TEXT NOT NULL,
                    queue_index INTEGER NOT NULL,
                    position_in_playlist INTEGER,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            logger.info("  ✓ Migration to v35 complete: player_queue_state table added")
        except Exception as e:
            logger.error(f"  ✗ Migration to v35 failed: {e}")
            conn.rollback()
            raise


def init_database() -> None:
    """Initialize the database with required tables."""
    db_path = get_database_path()
    logger.info(f"Initializing database at: {db_path}")

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
                top_level_artist TEXT,
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
            logger.info(
                f"Running database migrations from v{current_version} to v{SCHEMA_VERSION}"
            )
            migrate_database(conn, current_version)
        else:
            logger.debug(f"Database schema is up to date (v{current_version})")

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


def batch_add_soundcloud_likes(track_ids: list[int]) -> int:
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
        (
            track_id,
            "like",
            hour_of_day,
            day_of_week,
            "Synced from SoundCloud",
            "soundcloud",
        )
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


def batch_add_spotify_likes(track_ids: list[int]) -> int:
    """Bulk insert Spotify like markers for multiple tracks.

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
        (track_id, "like", hour_of_day, day_of_week, "Synced from Spotify", "spotify")
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


def get_track_ratings(track_id: int) -> list[dict[str, Any]]:
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


def get_track_notes(track_id: int) -> list[dict[str, Any]]:
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


def get_recent_ratings(limit: int = 10) -> list[dict[str, Any]]:
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


def get_rating_history(limit: int = 100) -> list[dict[str, Any]]:
    """Get rating history with full track information for interactive review.

    Args:
        limit: Maximum number of ratings to return

    Returns:
        List of rating dicts with fields:
        - rating_id: Rating record ID
        - track_id: Track ID
        - rating_type: Type of rating (like, love, archive, skip)
        - timestamp: When rating was created
        - context: Optional context text
        - source: Source of rating (user, soundcloud, spotify, etc.)
        - title: Track title
        - artist: Track artist
        - album: Track album
        - year: Track year
        - genre: Track genre
        - local_path: Track local file path
        - soundcloud_id: Track SoundCloud ID
        - spotify_id: Track Spotify ID
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                r.id as rating_id,
                r.track_id,
                r.rating_type,
                r.timestamp,
                r.context,
                r.source,
                t.title,
                t.artist,
                t.album,
                t.year,
                t.genre,
                t.local_path,
                t.soundcloud_id,
                t.spotify_id
            FROM ratings r
            JOIN tracks t ON r.track_id = t.id
            ORDER BY r.timestamp DESC
            LIMIT ?
        """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]


def delete_rating_by_id(rating_id: int) -> bool:
    """Delete a rating by its ID.

    Args:
        rating_id: ID of the rating record to delete

    Returns:
        True if rating was deleted, False otherwise
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            DELETE FROM ratings
            WHERE id = ?
        """,
            (rating_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


def get_recent_playback_sessions(
    limit: int = 50, source_filter: Optional[str] = None
) -> list[dict[str, Any]]:
    """Get recent listening sessions with track metadata.

    Args:
        limit: Maximum number of sessions to return
        source_filter: Optional source to filter by ('local', 'soundcloud', 'spotify', 'youtube').
                      If None or 'all', returns sessions from all sources.

    Returns:
        List of dicts with: id (track ID), session_id, track_id, title, artist, album,
                           genre, year, bpm, key_signature, local_path, soundcloud_id,
                           spotify_id, youtube_id, started_at, seconds_played, playlist_id
    """
    with get_db_connection() as conn:
        # Build WHERE clause for source filtering
        where_clause = ""
        params: list[Any] = []

        if source_filter and source_filter != "all":
            where_clause = "WHERE t.source = ?"
            params.append(source_filter)

        params.append(limit)

        cursor = conn.execute(
            f"""
            SELECT
                t.id, ls.session_id, ls.track_id, ls.started_at, ls.seconds_played,
                ls.playlist_id,
                t.title, t.artist, t.album, t.genre, t.year,
                t.bpm, t.key_signature, t.local_path,
                t.soundcloud_id, t.spotify_id, t.youtube_id
            FROM track_listen_sessions ls
            JOIN tracks t ON ls.track_id = t.id
            {where_clause}
            ORDER BY ls.started_at DESC
            LIMIT ?
        """,
            params,
        )
        return [dict(row) for row in cursor.fetchall()]


def get_archived_tracks() -> list[int]:
    """Get list of track IDs that have been archived."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT DISTINCT track_id
            FROM ratings
            WHERE rating_type = 'archive'
        """)
        return [row["track_id"] for row in cursor.fetchall()]


def get_rating_patterns(track_id: int) -> dict[str, Any]:
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


def get_library_analytics() -> dict[str, Any]:
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
    """Clean up old uncompleted playback sessions from legacy table."""
    with get_db_connection() as conn:
        # Remove sessions older than 24 hours that weren't properly ended
        conn.execute("""
            DELETE FROM playback_sessions
            WHERE ended_at IS NULL
            AND started_at < datetime('now', '-24 hours')
        """)
        conn.commit()


# Playback session tracking functions (new implementation)


def start_listen_session(track_id: int, playlist_id: Optional[int] = None) -> int:
    """Start a new listening session and return session ID.

    Args:
        track_id: ID of the track being played
        playlist_id: Optional ID of the playlist context

    Returns:
        Session ID for the new session
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO track_listen_sessions (track_id, play_date, playlist_id)
            VALUES (?, DATE('now'), ?)
        """,
            (track_id, playlist_id),
        )
        conn.commit()
        return cursor.lastrowid


def tick_listen_session(session_id: int, is_playing: bool) -> None:
    """Increment seconds_played for an active session if currently playing.

    Args:
        session_id: ID of the active session
        is_playing: Whether playback is currently active
    """
    if is_playing:
        with get_db_connection() as conn:
            conn.execute(
                """
                UPDATE track_listen_sessions
                SET seconds_played = seconds_played + 1
                WHERE session_id = ?
            """,
                (session_id,),
            )
            conn.commit()


def get_track_listen_stats(track_id: int) -> dict[str, Any]:
    """Get listening statistics for a track.

    Args:
        track_id: ID of the track

    Returns:
        Dict with play_count, total_seconds, effective_plays, last_played
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                COUNT(*) as play_count,
                SUM(s.seconds_played) as total_seconds,
                SUM(s.seconds_played) / t.duration as effective_plays,
                MAX(s.started_at) as last_played
            FROM track_listen_sessions s
            JOIN tracks t ON t.id = s.track_id
            WHERE s.track_id = ?
        """,
            (track_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else {}


def get_daily_listening_time(play_date: Optional[str] = None) -> float:
    """Get total listening time for a specific date.

    Args:
        play_date: Date in YYYY-MM-DD format, defaults to today

    Returns:
        Total seconds listened
    """
    date_filter = play_date or "DATE('now')"
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT SUM(seconds_played) as total_seconds
            FROM track_listen_sessions
            WHERE play_date = ?
        """,
            (date_filter,),
        )
        row = cursor.fetchone()
        return row["total_seconds"] or 0.0 if row else 0.0


def get_top_tracks_by_time(days: int = 30, limit: int = 20) -> list[dict[str, Any]]:
    """Get top tracks by listening time in the last N days.

    Args:
        days: Number of days to look back
        limit: Maximum number of tracks to return

    Returns:
        List of dicts with track_id and total_seconds
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT s.track_id, SUM(s.seconds_played) as total_seconds,
                   t.title, t.artist, t.album
            FROM track_listen_sessions s
            JOIN tracks t ON t.id = s.track_id
            WHERE s.play_date >= DATE('now', '-{} days')
            GROUP BY s.track_id
            ORDER BY total_seconds DESC
            LIMIT ?
        """.format(days),
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_playlist_listening_stats(playlist_id: int) -> dict[str, Any]:
    """Get listening statistics for a playlist.

    Args:
        playlist_id: ID of the playlist

    Returns:
        Dict with sessions, time, avg_session_length
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT COUNT(*) as sessions, SUM(seconds_played) as time
            FROM track_listen_sessions
            WHERE playlist_id = ?
        """,
            (playlist_id,),
        )
        row = cursor.fetchone()
        if row:
            stats = dict(row)
            stats["avg_session_length"] = (
                stats["time"] / stats["sessions"] if stats["sessions"] > 0 else 0
            )
            return stats
        return {}


def get_playlist_listening_stats_grouped() -> list[dict[str, Any]]:
    """Get listening statistics grouped by playlist.

    Returns:
        List of dicts with: playlist_id, sessions, total_seconds
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                playlist_id,
                COUNT(*) as sessions,
                SUM(seconds_played) as total_seconds
            FROM track_listen_sessions
            WHERE playlist_id IS NOT NULL
            GROUP BY playlist_id
        """
        )
        return [dict(row) for row in cursor.fetchall()]


def get_track_by_path(local_path: str) -> Optional[dict[str, Any]]:
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


def get_track_by_id(track_id: int) -> Optional[dict[str, Any]]:
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


def get_track_by_provider_id(
    provider: str, provider_id: str
) -> Optional[dict[str, Any]]:
    """Get track information by provider ID.

    Args:
        provider: Provider name ('soundcloud', 'spotify', 'youtube')
        provider_id: Provider-specific track ID

    Returns:
        Track dict or None if not found
    """
    column_map = {
        "soundcloud": "soundcloud_id",
        "spotify": "spotify_id",
        "youtube": "youtube_id",
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


def get_track_path_to_id_map() -> dict[str, int]:
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


def batch_upsert_tracks(tracks: list[Any]) -> tuple[int, int]:
    """Batch insert or update tracks in database (optimized for large libraries).

    This function is 30-50x faster than individual get_or_create_track() calls
    by using a single query to check existing tracks and batch INSERT/UPDATE operations.

    Args:
        tracks: List of Track objects from domain.library.models

    Returns:
        tuple of (added_count, updated_count)
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


# YouTube-specific track functions


def insert_youtube_track(
    local_path: str,
    youtube_id: str,
    title: str,
    artist: Optional[str],
    album: Optional[str],
    duration: float,
) -> int:
    """Insert a YouTube-sourced track into database.

    Sets:
    - source = 'youtube'
    - youtube_synced_at = current timestamp
    - youtube_id = provided video ID
    - local_path = path to downloaded file

    Args:
        local_path: Path to downloaded video file
        youtube_id: YouTube video ID (11 characters)
        title: Track title
        artist: Track artist (optional)
        album: Album name (optional)
        duration: Duration in seconds

    Returns:
        Track ID of newly inserted track
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tracks (
                local_path, youtube_id, title, artist, album, duration,
                source, youtube_synced_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'youtube', ?)
            """,
            (local_path, youtube_id, title, artist, album, duration, datetime.now()),
        )
        conn.commit()
        return cursor.lastrowid


def batch_insert_youtube_tracks(tracks_data: list[dict]) -> list[int]:
    """Batch insert multiple YouTube tracks efficiently.

    Uses SQLite RETURNING clause (requires SQLite 3.35+) to get all IDs in one query.

    Args:
        tracks_data: List of dicts with keys:
            local_path, youtube_id, title, artist, album, duration

    Returns:
        List of track IDs for inserted tracks (same order as input)

    Raises:
        sqlite3.IntegrityError: If any youtube_id already exists (transaction rolls back)
    """
    if not tracks_data:
        return []

    with get_db_connection() as conn:
        # Use RETURNING clause to get all IDs in one query
        placeholders = ", ".join(["(?, ?, ?, ?, ?, ?, 'youtube', ?)"] * len(tracks_data))

        # Flatten the data with youtube_synced_at timestamp
        synced_at = datetime.now()
        values = []
        for track in tracks_data:
            values.extend(
                [
                    track["local_path"],
                    track["youtube_id"],
                    track["title"],
                    track.get("artist"),
                    track.get("album"),
                    track["duration"],
                    synced_at,
                ]
            )

        cursor = conn.execute(
            f"""
            INSERT INTO tracks (
                local_path, youtube_id, title, artist, album, duration,
                source, youtube_synced_at
            )
            VALUES {placeholders}
            RETURNING id
            """,
            values,
        )

        # Extract IDs in order
        track_ids = [row[0] for row in cursor.fetchall()]
        conn.commit()

        return track_ids


def get_track_by_youtube_id(youtube_id: str) -> Optional[Track]:
    """Check if a YouTube video is already imported.

    Args:
        youtube_id: YouTube video ID (11 characters)

    Returns:
        Track object if found, None otherwise
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM tracks WHERE youtube_id = ?
            """,
            (youtube_id,),
        )
        row = cursor.fetchone()

        if row:
            return db_track_to_library_track(dict(row))

        return None


def get_existing_youtube_ids(youtube_ids: list[str]) -> set[str]:
    """Batch check which YouTube IDs already exist in database.

    Args:
        youtube_ids: List of YouTube video IDs to check

    Returns:
        Set of youtube_ids that already exist
    """
    if not youtube_ids:
        return set()

    with get_db_connection() as conn:
        # Build parameterized query dynamically
        placeholders = ", ".join("?" * len(youtube_ids))
        cursor = conn.execute(
            f"""
            SELECT youtube_id FROM tracks WHERE youtube_id IN ({placeholders})
            """,
            youtube_ids,
        )

        # Return set for O(1) lookup
        return {row["youtube_id"] for row in cursor.fetchall()}


def get_tracks_by_youtube_ids(youtube_ids: list[str]) -> list[Track]:
    """Batch retrieve tracks by YouTube IDs.

    More efficient than calling get_track_by_youtube_id() N times.

    Args:
        youtube_ids: List of YouTube video IDs to retrieve

    Returns:
        List of Track objects (order may not match input order)
    """
    if not youtube_ids:
        return []

    with get_db_connection() as conn:
        placeholders = ", ".join("?" * len(youtube_ids))
        cursor = conn.execute(
            f"""
            SELECT * FROM tracks WHERE youtube_id IN ({placeholders})
            """,
            youtube_ids,
        )

        return [db_track_to_library_track(dict(row)) for row in cursor.fetchall()]


# ============================================================================
# SoundCloud Track Functions (Streaming - no local_path)
# ============================================================================


def insert_soundcloud_track(
    soundcloud_id: str,
    source_url: str,
    title: str,
    artist: Optional[str],
    duration: float,
    genre: Optional[str] = None,
    bpm: Optional[float] = None,
) -> int:
    """Insert a SoundCloud streaming track into database.

    Unlike YouTube tracks, SoundCloud tracks are streamed (not downloaded),
    so local_path is NULL. The source_url stores the permalink for yt-dlp.

    Sets:
    - source = 'soundcloud'
    - soundcloud_synced_at = current timestamp
    - soundcloud_id = provided track ID
    - source_url = SoundCloud permalink (for yt-dlp)
    - local_path = NULL (streaming only)

    Args:
        soundcloud_id: SoundCloud track ID
        source_url: SoundCloud track permalink (e.g., https://soundcloud.com/artist/track)
        title: Track title
        artist: Track artist (optional)
        duration: Duration in seconds
        genre: Track genre (optional)
        bpm: Beats per minute (optional)

    Returns:
        Track ID of newly inserted track
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tracks (
                soundcloud_id, source_url, title, artist, duration,
                genre, bpm, source, soundcloud_synced_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'soundcloud', ?)
            RETURNING id
            """,
            (
                soundcloud_id,
                source_url,
                title,
                artist,
                duration,
                genre,
                bpm,
                datetime.now(),
            ),
        )
        row = cursor.fetchone()
        conn.commit()
        return row[0]


def batch_insert_soundcloud_tracks(tracks_data: list[dict]) -> list[int]:
    """Batch insert multiple SoundCloud streaming tracks efficiently.

    Uses SQLite RETURNING clause (requires SQLite 3.35+) to get all IDs in one query.

    Args:
        tracks_data: List of dicts with keys:
            soundcloud_id, source_url, title, artist, duration, genre (optional), bpm (optional)

    Returns:
        List of track IDs for inserted tracks (same order as input)

    Raises:
        sqlite3.IntegrityError: If any soundcloud_id already exists (transaction rolls back)
    """
    if not tracks_data:
        return []

    with get_db_connection() as conn:
        # Use RETURNING clause to get all IDs in one query
        placeholders = ", ".join(
            ["(?, ?, ?, ?, ?, ?, ?, 'soundcloud', ?)"] * len(tracks_data)
        )

        # Flatten the data with soundcloud_synced_at timestamp
        synced_at = datetime.now()
        values = []
        for track in tracks_data:
            values.extend(
                [
                    track["soundcloud_id"],
                    track["source_url"],
                    track["title"],
                    track.get("artist"),
                    track["duration"],
                    track.get("genre"),
                    track.get("bpm"),
                    synced_at,
                ]
            )

        cursor = conn.execute(
            f"""
            INSERT INTO tracks (
                soundcloud_id, source_url, title, artist, duration,
                genre, bpm, source, soundcloud_synced_at
            )
            VALUES {placeholders}
            RETURNING id
            """,
            values,
        )

        # Extract IDs in order
        track_ids = [row[0] for row in cursor.fetchall()]
        conn.commit()

        return track_ids


def get_track_by_soundcloud_id(soundcloud_id: str) -> Optional[Track]:
    """Check if a SoundCloud track is already imported.

    Args:
        soundcloud_id: SoundCloud track ID

    Returns:
        Track object if found, None otherwise
    """
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM tracks WHERE soundcloud_id = ?
            """,
            (soundcloud_id,),
        )
        row = cursor.fetchone()

        if row:
            return db_track_to_library_track(dict(row))

        return None


def get_existing_soundcloud_ids(soundcloud_ids: list[str]) -> set[str]:
    """Batch check which SoundCloud IDs already exist in database.

    Args:
        soundcloud_ids: List of SoundCloud track IDs to check

    Returns:
        Set of soundcloud_ids that already exist
    """
    if not soundcloud_ids:
        return set()

    with get_db_connection() as conn:
        # Build parameterized query dynamically
        placeholders = ", ".join("?" * len(soundcloud_ids))
        cursor = conn.execute(
            f"""
            SELECT soundcloud_id FROM tracks WHERE soundcloud_id IN ({placeholders})
            """,
            soundcloud_ids,
        )

        # Return set for O(1) lookup
        return {row["soundcloud_id"] for row in cursor.fetchall()}


def get_tracks_by_soundcloud_ids(soundcloud_ids: list[str]) -> list[Track]:
    """Batch retrieve tracks by SoundCloud IDs.

    More efficient than calling get_track_by_soundcloud_id() N times.

    Args:
        soundcloud_ids: List of SoundCloud track IDs to retrieve

    Returns:
        List of Track objects (order may not match input order)
    """
    if not soundcloud_ids:
        return []

    with get_db_connection() as conn:
        placeholders = ", ".join("?" * len(soundcloud_ids))
        cursor = conn.execute(
            f"""
            SELECT * FROM tracks WHERE soundcloud_id IN ({placeholders})
            """,
            soundcloud_ids,
        )

        return [db_track_to_library_track(dict(row)) for row in cursor.fetchall()]


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


def get_unprocessed_notes() -> list[dict[str, Any]]:
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


def get_all_tracks() -> list[dict[str, Any]]:
    """Get all tracks from the database."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT * FROM tracks
            ORDER BY artist, album, title
        """)
        return [dict(row) for row in cursor.fetchall()]


def filter_tracks_by_library(
    tracks: list[dict[str, Any]], library: str
) -> list[dict[str, Any]]:
    """Filter tracks to those belonging to the specified library/provider.

    Args:
        tracks: List of track dictionaries
        library: Provider name ('local', 'soundcloud', 'spotify', 'youtube', 'all')

    Returns:
        Filtered list of tracks
    """
    if library == "local":
        return [t for t in tracks if t.get("local_path")]
    elif library == "soundcloud":
        return [t for t in tracks if t.get("soundcloud_id")]
    elif library == "spotify":
        return [t for t in tracks if t.get("spotify_id")]
    elif library == "youtube":
        return [t for t in tracks if t.get("youtube_id")]
    else:  # "all" or unknown
        return tracks


def get_available_track_paths() -> list[str]:
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


def get_available_tracks() -> list[dict[str, Any]]:
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


def get_all_tracks_with_metadata() -> list[dict[str, Any]]:
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


def get_unique_genres() -> list[tuple[str, int]]:
    """Get all unique genres with counts, sorted by count desc."""
    with get_db_connection() as conn:
        cursor = conn.execute("""
            SELECT genre, COUNT(*) as count
            FROM tracks
            WHERE genre IS NOT NULL AND genre != ''
            GROUP BY genre
            ORDER BY count DESC
        """)
        return [(row["genre"], row["count"]) for row in cursor.fetchall()]


def db_track_to_library_track(db_track: dict[str, Any]) -> Track:
    """Convert database track record to Track object."""
    # Import here to avoid circular imports
    from ..domain import library

    # Map database columns to Track fields
    # Ensure file_path is never None - use empty string for provider tracks without local files
    local_path = db_track.get("local_path") or ""

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
        source_url=db_track.get("source_url"),
        id=db_track.get("id"),
    )


# Tag management functions


def add_tags(
    track_id: int,
    tags: list[str],
    source: str = "user",
    confidence: Optional[float] = None,
    reasoning: Optional[dict[str, str]] = None,
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
) -> list[dict[str, Any]]:
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


def get_track_tags_batch(
    track_ids: list[int], include_blacklisted: bool = False
) -> dict[int, list[dict[str, Any]]]:
    """Get tags for multiple tracks in a single query.

    Args:
        track_ids: List of track IDs to fetch tags for
        include_blacklisted: Include blacklisted tags in results

    Returns:
        Dictionary mapping track_id to list of tag dictionaries
    """
    from collections import defaultdict

    if not track_ids:
        return {}

    result: dict[int, list[dict[str, Any]]] = defaultdict(list)
    blacklist_filter = "" if include_blacklisted else "AND blacklisted = FALSE"

    with get_db_connection() as conn:
        placeholders = ",".join("?" * len(track_ids))
        cursor = conn.execute(
            f"""
            SELECT track_id, tag_name, source, confidence, created_at, blacklisted, reasoning
            FROM tags
            WHERE track_id IN ({placeholders}) {blacklist_filter}
            ORDER BY track_id, created_at DESC
        """,
            track_ids,
        )

        for row in cursor.fetchall():
            row_dict = dict(row)
            track_id = row_dict.pop("track_id")
            result[track_id].append(row_dict)

    return dict(result)


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


def get_ai_usage_stats(days: Optional[int] = None) -> dict[str, Any]:
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


def get_tracks_needing_analysis() -> list[dict[str, Any]]:
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
    provider: str, auth_data: dict[str, Any], config: dict[str, Any]
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


def load_provider_state(provider: str) -> Optional[dict[str, Any]]:
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
    """Update track metadata fields in database AND file.

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
        # Get local_path for file writing
        cursor = conn.execute("SELECT local_path FROM tracks WHERE id = ?", (track_id,))
        row = cursor.fetchone()
        local_path = row["local_path"] if row else None

        # Update database with metadata_updated_at timestamp
        conn.execute(
            f"""
            UPDATE tracks
            SET {set_clause}, metadata_updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            values,
        )
        conn.commit()

    # Write to file if local_path exists
    if local_path:
        import os

        if os.path.exists(local_path):
            from music_minion.domain.library.metadata import write_metadata_to_file

            # Map DB fields to file write function parameters
            # Note: key_signature -> key, remix_artist is not written to file
            file_fields = {
                "title": validated_fields.get("title"),
                "artist": validated_fields.get("artist"),
                "album": validated_fields.get("album"),
                "genre": validated_fields.get("genre"),
                "year": validated_fields.get("year"),
                "bpm": validated_fields.get("bpm"),
                "key": validated_fields.get("key_signature"),
            }

            # Only pass non-None values that were actually updated
            file_fields = {
                k: v
                for k, v in file_fields.items()
                if k in fields or (k == "key" and "key_signature" in fields)
            }

            if file_fields:
                write_metadata_to_file(local_path, **file_fields)

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
