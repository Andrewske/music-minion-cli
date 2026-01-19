#!/usr/bin/env python3
"""
Import CSV playlist directly.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from music_minion.context import AppContext
from music_minion.core import config, database
from music_minion.commands import playlist
from music_minion.domain.playback.player import PlayerState


def main():
    if len(sys.argv) != 2:
        print("Usage: python import_csv.py <csv_file>")
        sys.exit(1)

    csv_path = sys.argv[1]

    # Initialize
    current_config = config.load_config()
    database.init_database()

    # Load tracks
    db_tracks = database.get_all_tracks()
    tracks = [database.db_track_to_library_track(track) for track in (db_tracks or [])]

    # Create context
    ctx = AppContext(
        config=current_config, music_tracks=tracks, player_state=PlayerState()
    )

    print(f"Importing CSV: {csv_path}")

    # Import playlist
    ctx, success = playlist.handle_playlist_import_command(ctx, [csv_path])

    if success:
        print("✅ CSV playlist imported successfully!")
    else:
        print("❌ Failed to import CSV playlist")
        sys.exit(1)


if __name__ == "__main__":
    main()
