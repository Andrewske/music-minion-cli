#!/usr/bin/env python3
"""
Check the current state of track ID 5981
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

    # Check track ID 5981
    track = database.get_track_by_id(5981)
    if track:
        print("Current database state for Track ID 5981:")
        print(f"Title: {track.get('title', 'None')}")
        print(f"Artist: {track.get('artist', 'None')}")
        print(f"BPM: {track.get('bpm', 'None')}")
        print(f"Local path: {track.get('local_path', 'None')}")

        # Check file metadata
        import os
        from mutagen import File as MutagenFile

        local_path = track.get("local_path")
        if local_path and os.path.exists(local_path):
            try:
                audio = MutagenFile(local_path)
                if audio:
                    print("\nFile metadata:")
                    print(
                        f"Title: {audio.get('title', ['None'])[0] if audio.get('title') else 'None'}"
                    )
                    print(
                        f"Artist: {audio.get('artist', ['None'])[0] if audio.get('artist') else 'None'}"
                    )
                    print(
                        f"BPM: {audio.get('bpm', ['None'])[0] if audio.get('bpm') else 'None'}"
                    )
                else:
                    print("Could not read file metadata")
            except Exception as e:
                print(f"Error reading file metadata: {e}")
        else:
            print("Local file not found")
    else:
        print("Track ID 5981 not found in database")


if __name__ == "__main__":
    main()
