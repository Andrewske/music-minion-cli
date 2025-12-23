#!/usr/bin/env python3
"""
Debug why track 5981 didn't update during CSV import
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from music_minion.core import config, database


def main():
    # Initialize database
    current_config = config.load_config()
    database.init_database()

    # Test manual update of track 5981
    print("Testing manual update of track 5981...")

    # Current state before update
    track = database.get_track_by_id(5981)
    if track:
        print("Before update:")
        print(f"  Title: {track.get('title')}")
        print(f"  Artist: {track.get('artist')}")
        print(f"  BPM: {track.get('bpm')}")

        # Try to update it
        print("\nAttempting update...")
        success = database.update_track_metadata(
            5981, title="Rockstar 101 (ALLEYCVT FLIP)", artist="Rihanna"
        )

        print(f"Update result: {success}")

        # Check state after update
        track = database.get_track_by_id(5981)
        if track:
            print("After update:")
            print(f"  Title: {track.get('title')}")
            print(f"  Artist: {track.get('artist')}")
            print(f"  BPM: {track.get('bpm')}")
        else:
            print("Track not found after update")
    else:
        print("Track 5981 not found")


if __name__ == "__main__":
    main()
