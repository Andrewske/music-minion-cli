#!/usr/bin/env python3
"""
Simple script to import a playlist directly without the interactive UI.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from music_minion.context import AppContext
from music_minion.core import config, database
from music_minion.commands import playlist
from music_minion.domain.playlists.importers import resolve_relative_path, import_m3u
from music_minion.domain.playlists.crud import add_track_to_playlist
from music_minion.domain.playback.player import PlayerState


def debug_import():
    """Debug the import process step by step."""
    playlist_file = "NYE 25_fixed.m3u8"
    playlist_path = Path(playlist_file).expanduser()

    # Initialize config and database
    current_config = config.load_config()
    database.init_database()

    library_root = Path(current_config.music.library_paths[0]).expanduser()
    print(f"Library root: {library_root}")

    # Test path resolution for first track
    with open(playlist_path, "r") as f:
        lines = f.readlines()

    track_paths = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#"):
            continue
        track_paths.append(line)

    print(f"Found {len(track_paths)} track paths")
    if track_paths:
        first_track = track_paths[0]
        print(f"First track path: {first_track}")

        resolved = resolve_relative_path(playlist_path, first_track, library_root)
        print(f"Resolved to: {resolved}")
        print(f"Resolved exists: {resolved.exists() if resolved else False}")

        if resolved:
            # Test database lookup
            with database.get_db_connection() as conn:
                cursor = conn.execute(
                    "SELECT id FROM tracks WHERE local_path = ?", (str(resolved),)
                )
                row = cursor.fetchone()
                print(f"Database lookup result: {dict(row) if row else None}")

                if row:
                    track_id = row["id"]
                    print(f"Track ID: {track_id}")

                    # Test adding to playlist
                    # First create a test playlist
                    from music_minion.domain.playlists.crud import create_playlist

                    try:
                        test_playlist_id = create_playlist(
                            "debug_test", "manual", "Debug playlist"
                        )
                        print(f"Created test playlist: {test_playlist_id}")

                        result = add_track_to_playlist(test_playlist_id, track_id)
                        print(f"Add track result: {result}")

                    except Exception as e:
                        print(f"Error creating test playlist: {e}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python import_playlist.py <playlist_file>")
        sys.exit(1)

    # Run debug first
    debug_import()

    playlist_file = sys.argv[1]

    # Initialize config and database
    current_config = config.load_config()
    database.init_database()

    # Load tracks from database
    db_tracks = database.get_all_tracks()
    tracks = (
        [database.db_track_to_library_track(track) for track in db_tracks]
        if db_tracks
        else []
    )

    # Create initial context
    ctx = AppContext(
        config=current_config, music_tracks=tracks, player_state=PlayerState()
    )

    # Import the playlist
    try:
        ctx, success = playlist.handle_playlist_import_command(ctx, [playlist_file])
        if success:
            print("Playlist imported successfully!")
        else:
            print("Failed to import playlist")
            sys.exit(1)
    except Exception as e:
        print(f"Error importing playlist: {e}")
        sys.exit(1)

    playlist_file = sys.argv[1]

    # Initialize config and database
    current_config = config.load_config()
    database.init_database()

    # Load tracks from database
    db_tracks = database.get_all_tracks()
    tracks = (
        [database.db_track_to_library_track(track) for track in db_tracks]
        if db_tracks
        else []
    )

    # Create initial context
    ctx = AppContext(
        config=current_config, music_tracks=tracks, player_state=PlayerState()
    )

    # Import the playlist
    try:
        ctx, success = playlist.handle_playlist_import_command(ctx, [playlist_file])
        if success:
            print("Playlist imported successfully!")
        else:
            print("Failed to import playlist")
            sys.exit(1)
    except Exception as e:
        print(f"Error importing playlist: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
