#!/usr/bin/env python3
"""
Check what specific changes were made in the CSV vs current database state.
"""

import sys
from pathlib import Path
import csv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from music_minion.core import config, database


def main():
    csv_path = "/home/kevin/Music/EDM/playlists/NYE 25_final.csv"

    # Initialize database
    current_config = config.load_config()
    database.init_database()

    # Read CSV
    changes_found = 0
    total_tracks = 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_tracks += 1

            # Get current track data from database
            track_id = int(row["id"])
            db_track = database.get_track_by_id(track_id)

            if not db_track:
                print(f"Track ID {track_id} not found in database")
                continue

            # Check for differences
            differences = []

            # Check metadata fields that can be updated
            fields_to_check = [
                "title",
                "artist",
                "remix_artist",
                "album",
                "genre",
                "year",
                "bpm",
                "key_signature",
            ]

            for field in fields_to_check:
                csv_value = row.get(field, "").strip()
                db_value = str(db_track.get(field, ""))

                # Handle None values
                if db_value == "None":
                    db_value = ""

                # Handle type conversions for comparison
                if field == "year" and csv_value:
                    try:
                        csv_value = str(int(csv_value))
                    except:
                        pass
                elif field == "bpm" and csv_value:
                    try:
                        csv_value = str(int(float(csv_value)))
                    except:
                        pass

                if csv_value != db_value:
                    differences.append(f"{field}: '{db_value}' -> '{csv_value}'")

            if differences:
                changes_found += 1
                print(f"Track ID {track_id} ({db_track.get('title', 'Unknown')}):")
                for diff in differences:
                    print(f"  • {diff}")
                print()

    print(
        f"Summary: {changes_found} tracks with changes out of {total_tracks} total tracks"
    )


if __name__ == "__main__":
    main()
