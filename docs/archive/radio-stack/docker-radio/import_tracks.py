#!/usr/bin/env python3
"""
Import tracks from local SQLite database to PostgreSQL.

Performs incremental sync - only updates records where SQLite is newer.

Usage:
    DATABASE_URL=postgres://... python import_tracks.py
    DATABASE_URL=postgres://... python import_tracks.py --full  # Force full sync
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

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


def parse_timestamp(ts) -> datetime | None:
    """Parse timestamp from string or return datetime as-is."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts
    try:
        return datetime.fromisoformat(ts.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None


def import_from_sqlite(sqlite_path: Path, pg_url: str, full_sync: bool = False, since: datetime | None = None) -> None:
    """Import tracks, playlists, and stations from SQLite to PostgreSQL.

    Args:
        sqlite_path: Path to SQLite database
        pg_url: PostgreSQL connection URL
        full_sync: If True, sync all records. If False, only sync changed records.
        since: If provided, only sync records modified after this datetime.
    """
    import psycopg2

    print(f"Importing from: {sqlite_path}")
    print(f"To PostgreSQL: {pg_url.split('@')[1] if '@' in pg_url else pg_url}")
    mode = "Full sync" if full_sync else f"Since {since.date()}" if since else "Incremental (changed only)"
    print(f"Mode: {mode}")

    # Connect to SQLite
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    # Connect to PostgreSQL
    pg_conn = psycopg2.connect(pg_url)
    pg_cursor = pg_conn.cursor()

    # === TRACKS ===
    print("\nSyncing tracks...")

    # Get existing tracks from PostgreSQL with their updated_at
    pg_timestamps: dict[int, datetime | None] = {}
    if not full_sync:
        pg_cursor.execute("SELECT id, updated_at FROM tracks")
        for row in pg_cursor.fetchall():
            pg_timestamps[row[0]] = row[1]
        print(f"  Found {len(pg_timestamps)} existing tracks in PostgreSQL")

    # Get all tracks from SQLite
    sqlite_cursor = sqlite_conn.execute("""
        SELECT id, local_path, title, artist, album, genre, year, duration,
               key_signature, bpm, created_at, updated_at
        FROM tracks
    """)

    inserted = 0
    updated = 0
    skipped = 0

    for row in sqlite_cursor:
        track_id = row["id"]
        sqlite_updated = parse_timestamp(row["updated_at"])
        pg_updated = pg_timestamps.get(track_id)

        # Skip logic: full_sync overrides all, since forces update for recent tracks
        if not full_sync:
            # If using --since, force sync tracks modified after that date
            if since and sqlite_updated and sqlite_updated >= since:
                pass  # Force sync this track
            elif pg_updated and sqlite_updated and pg_updated >= sqlite_updated:
                skipped += 1
                continue

        is_new = track_id not in pg_timestamps

        pg_cursor.execute("""
            INSERT INTO tracks (id, local_path, title, artist, album, genre, year,
                               duration, key_signature, bpm, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                local_path = EXCLUDED.local_path,
                title = EXCLUDED.title,
                artist = EXCLUDED.artist,
                album = EXCLUDED.album,
                genre = EXCLUDED.genre,
                year = EXCLUDED.year,
                duration = EXCLUDED.duration,
                key_signature = EXCLUDED.key_signature,
                bpm = EXCLUDED.bpm,
                updated_at = EXCLUDED.updated_at
        """, sanitize_row(tuple(row)))

        if is_new:
            inserted += 1
        else:
            updated += 1

        if (inserted + updated) % 100 == 0:
            print(f"  Processing... {inserted} new, {updated} updated, {skipped} skipped")

    pg_cursor.execute("SELECT setval('tracks_id_seq', COALESCE((SELECT MAX(id) FROM tracks), 0) + 1, false)")
    print(f"  Tracks: {inserted} new, {updated} updated, {skipped} unchanged")

    # === PLAYLISTS ===
    print("\nSyncing playlists...")

    pg_playlist_timestamps: dict[int, datetime | None] = {}
    if not full_sync:
        pg_cursor.execute("SELECT id, updated_at FROM playlists")
        for row in pg_cursor.fetchall():
            pg_playlist_timestamps[row[0]] = row[1]

    sqlite_cursor = sqlite_conn.execute("""
        SELECT id, name, type, description, track_count, created_at, updated_at
        FROM playlists
    """)

    pl_inserted = 0
    pl_updated = 0
    pl_skipped = 0

    for row in sqlite_cursor:
        playlist_id = row["id"]
        sqlite_updated = parse_timestamp(row["updated_at"])
        pg_updated = pg_playlist_timestamps.get(playlist_id)

        if not full_sync and pg_updated and sqlite_updated:
            if pg_updated >= sqlite_updated:
                pl_skipped += 1
                continue

        is_new = playlist_id not in pg_playlist_timestamps

        pg_cursor.execute("""
            INSERT INTO playlists (id, name, type, description, track_count, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                type = EXCLUDED.type,
                description = EXCLUDED.description,
                track_count = EXCLUDED.track_count,
                updated_at = EXCLUDED.updated_at
        """, tuple(row))

        if is_new:
            pl_inserted += 1
        else:
            pl_updated += 1

    pg_cursor.execute("SELECT setval('playlists_id_seq', COALESCE((SELECT MAX(id) FROM playlists), 0) + 1, false)")
    print(f"  Playlists: {pl_inserted} new, {pl_updated} updated, {pl_skipped} unchanged")

    # === PLAYLIST_TRACKS ===
    print("\nSyncing playlist_tracks...")

    # Get existing playlist_tracks from PostgreSQL
    existing_pt: set[tuple[int, int]] = set()
    if not full_sync:
        pg_cursor.execute("SELECT playlist_id, track_id FROM playlist_tracks")
        for row in pg_cursor.fetchall():
            existing_pt.add((row[0], row[1]))

    sqlite_cursor = sqlite_conn.execute("""
        SELECT playlist_id, track_id, position, added_at
        FROM playlist_tracks
    """)

    pt_inserted = 0
    pt_skipped = 0

    for row in sqlite_cursor:
        key = (row["playlist_id"], row["track_id"])

        if not full_sync and key in existing_pt:
            pt_skipped += 1
            continue

        pg_cursor.execute("""
            INSERT INTO playlist_tracks (playlist_id, track_id, position, added_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (playlist_id, track_id) DO NOTHING
        """, tuple(row))
        pt_inserted += 1

    print(f"  Playlist tracks: {pt_inserted} new, {pt_skipped} existing")

    # === STATIONS ===
    print("\nSyncing stations...")

    pg_station_timestamps: dict[int, datetime | None] = {}
    if not full_sync:
        pg_cursor.execute("SELECT id, updated_at FROM stations")
        for row in pg_cursor.fetchall():
            pg_station_timestamps[row[0]] = row[1]

    sqlite_cursor = sqlite_conn.execute("""
        SELECT id, name, playlist_id, mode, is_active, created_at, updated_at
        FROM stations
    """)

    st_inserted = 0
    st_updated = 0
    st_skipped = 0

    for row in sqlite_cursor:
        station_id = row["id"]
        sqlite_updated = parse_timestamp(row["updated_at"])
        pg_updated = pg_station_timestamps.get(station_id)

        if not full_sync and pg_updated and sqlite_updated:
            if pg_updated >= sqlite_updated:
                st_skipped += 1
                continue

        is_new = station_id not in pg_station_timestamps

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

        if is_new:
            st_inserted += 1
        else:
            st_updated += 1

    pg_cursor.execute("SELECT setval('stations_id_seq', COALESCE((SELECT MAX(id) FROM stations), 0) + 1, false)")
    print(f"  Stations: {st_inserted} new, {st_updated} updated, {st_skipped} unchanged")

    # Commit and close
    pg_conn.commit()
    pg_cursor.close()
    pg_conn.close()
    sqlite_conn.close()

    print("\n✓ Sync complete!")


def schema_exists(pg_url: str) -> bool:
    """Check if the required tables already exist in PostgreSQL."""
    import psycopg2

    try:
        conn = psycopg2.connect(pg_url)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM pg_tables WHERE tablename = 'tracks'
            ) AND EXISTS (
                SELECT FROM pg_tables WHERE tablename = 'stations'
            )
        """)
        result = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return result
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Import tracks to PostgreSQL")
    parser.add_argument("--full", action="store_true",
                       help="Force full sync (default: incremental)")
    parser.add_argument("--since", type=str, metavar="DATE",
                       help="Sync tracks modified since DATE (YYYY-MM-DD or 'today')")
    parser.add_argument("--sqlite", type=Path, default=get_sqlite_db_path(),
                       help="SQLite database path (default: ~/.local/share/music-minion/music_minion.db)")
    args = parser.parse_args()

    # Parse --since date
    since_dt: datetime | None = None
    if args.since:
        if args.since.lower() == "today":
            since_dt = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            since_dt = datetime.fromisoformat(args.since)

    pg_url = os.environ.get("DATABASE_URL")
    if not pg_url:
        print("Error: DATABASE_URL environment variable required")
        sys.exit(1)

    # Initialize PostgreSQL schema (skip if tables exist)
    os.environ["DATABASE_URL"] = pg_url
    if schema_exists(pg_url):
        print("Schema exists, skipping initialization...")
    else:
        from music_minion.core.db_adapter import init_postgres_schema
        print("Initializing PostgreSQL schema...")
        init_postgres_schema()

    if not args.sqlite.exists():
        print(f"Error: SQLite database not found: {args.sqlite}")
        sys.exit(1)

    import_from_sqlite(args.sqlite, pg_url, full_sync=args.full, since=since_dt)


if __name__ == "__main__":
    main()
