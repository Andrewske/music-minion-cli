#!/usr/bin/env python3
"""
Quick script to check current playlists and help with CSV import.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from music_minion.core import config, database
from music_minion.domain.playlists import crud as playlists_crud


def main():
    # Initialize config and database
    current_config = config.load_config()
    database.init_database()

    # Get all playlists
    playlists = playlists_crud.get_all_playlists()
    if playlists:
        print("Current playlists:")
        for pl in playlists:
            print(f"  - {pl['name']} ({pl['track_count']} tracks)")
        print()
    else:
        print("No playlists found.")
        print()

    # Check for CSV files in common locations
    csv_files = []
    search_paths = [
        Path.home() / "Music",
        Path.home() / "Music" / "EDM" / "playlists",
        Path.cwd(),
    ]

    for path in search_paths:
        if path.exists():
            csvs = list(path.glob("*.csv"))
            csv_files.extend(csvs)

    if csv_files:
        print("Found CSV files:")
        for csv_file in csv_files:
            print(f"  - {csv_file}")
        print()
    else:
        print("No CSV files found in common locations.")

    # Show M3U8 files as alternative
    m3u8_files = list(Path.cwd().glob("*.m3u8"))
    if m3u8_files:
        print("Found M3U8 playlist files (can import these instead):")
        for m3u8_file in m3u8_files:
            print(f"  - {m3u8_file}")
        print()

    print("Options:")
    print("1. Export existing playlist to CSV: playlist export <name> csv")
    print("2. Import M3U8 playlist: playlist import <m3u8_file>")
    print("3. Create CSV manually with track changes")
    print("4. Import existing CSV if you have one")


if __name__ == "__main__":
    main()
