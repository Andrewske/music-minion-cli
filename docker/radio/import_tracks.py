#!/usr/bin/env python3
"""
Import tracks from local SQLite database to PostgreSQL.

Usage:
    DATABASE_URL=postgres://... python import_tracks.py

Or with music scan:
    DATABASE_URL=postgres://... python import_tracks.py --scan /path/to/music
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


def get_sqlite_db_path() -> Path:
    """Get default SQLite database path."""
    data_dir = Path.home() / ".local" / "share" / "music-minion"
    return data_dir / "music_minion.db"


def sanitize_value(val):
    """Remove NUL characters from strings."""
    if isinstance(val, str):
        return val.replace('\x00', '')
    return val


def sanitize_row(row):
    """Sanitize all values in a row."""
    return tuple(sanitize_value(v) for v in row)


def import_from_sqlite(sqlite_path: Path, pg_url: str) -> None:
    """Import tracks, playlists, and stations from SQLite to PostgreSQL."""
    import psycopg2

    print(f"Importing from: {sqlite_path}")
    print(f"To PostgreSQL: {pg_url.split('@')[1] if '@' in pg_url else pg_url}")

    # Connect to SQLite
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    # Connect to PostgreSQL
    pg_conn = psycopg2.connect(pg_url)
    pg_cursor = pg_conn.cursor()

    # Import tracks
    print("\nImporting tracks...")
    sqlite_cursor = sqlite_conn.execute("""
        SELECT id, local_path, title, artist, album, genre, year, duration,
               key_signature, bpm, created_at, updated_at
        FROM tracks
    """)

    track_count = 0
    for row in sqlite_cursor:
        pg_cursor.execute("""
            INSERT INTO tracks (id, local_path, title, artist, album, genre, year,
                               duration, key_signature, bpm, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                local_path = EXCLUDED.local_path,
                title = EXCLUDED.title,
                artist = EXCLUDED.artist,
                updated_at = EXCLUDED.updated_at
        """, sanitize_row(tuple(row)))
        track_count += 1
        if track_count % 100 == 0:
            print(f"  {track_count} tracks...")

    # Reset sequence
    pg_cursor.execute("SELECT setval('tracks_id_seq', COALESCE((SELECT MAX(id) FROM tracks), 0) + 1, false)")
    print(f"  Imported {track_count} tracks")

    # Import playlists
    print("\nImporting playlists...")
    sqlite_cursor = sqlite_conn.execute("""
        SELECT id, name, type, description, track_count, created_at, updated_at
        FROM playlists
    """)

    playlist_count = 0
    for row in sqlite_cursor:
        pg_cursor.execute("""
            INSERT INTO playlists (id, name, type, description, track_count, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                track_count = EXCLUDED.track_count,
                updated_at = EXCLUDED.updated_at
        """, tuple(row))
        playlist_count += 1

    pg_cursor.execute("SELECT setval('playlists_id_seq', COALESCE((SELECT MAX(id) FROM playlists), 0) + 1, false)")
    print(f"  Imported {playlist_count} playlists")

    # Import playlist_tracks
    print("\nImporting playlist_tracks...")
    sqlite_cursor = sqlite_conn.execute("""
        SELECT playlist_id, track_id, position, added_at
        FROM playlist_tracks
    """)

    pt_count = 0
    for row in sqlite_cursor:
        pg_cursor.execute("""
            INSERT INTO playlist_tracks (playlist_id, track_id, position, added_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (playlist_id, track_id) DO NOTHING
        """, tuple(row))
        pt_count += 1

    print(f"  Imported {pt_count} playlist tracks")

    # Import stations
    print("\nImporting stations...")
    sqlite_cursor = sqlite_conn.execute("""
        SELECT id, name, playlist_id, mode, is_active, created_at, updated_at
        FROM stations
    """)

    station_count = 0
    for row in sqlite_cursor:
        row_data = tuple(row)
        # Convert is_active from SQLite integer (0/1) to Python bool for PostgreSQL
        row_data = row_data[:4] + (bool(row_data[4]),) + row_data[5:]
        pg_cursor.execute("""
            INSERT INTO stations (id, name, playlist_id, mode, is_active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                playlist_id = EXCLUDED.playlist_id,
                mode = EXCLUDED.mode,
                is_active = EXCLUDED.is_active,
                updated_at = EXCLUDED.updated_at
        """, row_data)
        station_count += 1

    pg_cursor.execute("SELECT setval('stations_id_seq', COALESCE((SELECT MAX(id) FROM stations), 0) + 1, false)")
    print(f"  Imported {station_count} stations")

    # Commit and close
    pg_conn.commit()
    pg_cursor.close()
    pg_conn.close()
    sqlite_conn.close()

    print("\n✓ Import complete!")


def scan_and_import(music_path: Path, pg_url: str) -> None:
    """Scan music directory and import tracks to PostgreSQL."""
    from music_minion.core.config import Config, MusicConfig
    from music_minion.domain.library.scanner import scan_directory

    import psycopg2

    print(f"Scanning: {music_path}")

    # Scan tracks
    music_config = MusicConfig(library_paths=[str(music_path)])
    config = Config(music=music_config)
    tracks = scan_directory(music_path, config)
    print(f"Found {len(tracks)} tracks")

    # Connect to PostgreSQL
    pg_conn = psycopg2.connect(pg_url)
    pg_cursor = pg_conn.cursor()

    # Insert tracks
    print("\nImporting to PostgreSQL...")
    for i, track in enumerate(tracks):
        pg_cursor.execute("""
            INSERT INTO tracks (local_path, title, artist, album, genre, year,
                               duration, key_signature, bpm)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (local_path) DO UPDATE SET
                title = EXCLUDED.title,
                artist = EXCLUDED.artist,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
        """, (
            track.local_path, track.title, track.artist, track.album,
            track.genre, track.year, track.duration, track.key_signature, track.bpm
        ))

        if (i + 1) % 100 == 0:
            print(f"  {i + 1} tracks...")

    pg_conn.commit()
    pg_cursor.close()
    pg_conn.close()

    print(f"\n✓ Imported {len(tracks)} tracks")


def main():
    parser = argparse.ArgumentParser(description="Import tracks to PostgreSQL")
    parser.add_argument("--scan", type=Path, help="Scan and import from music directory")
    parser.add_argument("--sqlite", type=Path, default=get_sqlite_db_path(),
                       help="SQLite database path (default: ~/.local/share/music-minion/music_minion.db)")
    args = parser.parse_args()

    pg_url = os.environ.get("DATABASE_URL")
    if not pg_url:
        print("Error: DATABASE_URL environment variable required")
        sys.exit(1)

    # Initialize PostgreSQL schema
    from music_minion.core.db_adapter import init_postgres_schema
    os.environ["DATABASE_URL"] = pg_url  # Ensure it's set
    print("Initializing PostgreSQL schema...")
    init_postgres_schema()

    if args.scan:
        scan_and_import(args.scan, pg_url)
    else:
        if not args.sqlite.exists():
            print(f"Error: SQLite database not found: {args.sqlite}")
            sys.exit(1)
        import_from_sqlite(args.sqlite, pg_url)


if __name__ == "__main__":
    main()
