#!/usr/bin/env python3
"""
Import track metadata changes from CSV file.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from music_minion.domain.playlists.importers import import_playlist_metadata_csv


def main():
    if len(sys.argv) != 2:
        print("Usage: python import_metadata_csv.py <csv_file>")
        sys.exit(1)

    csv_path = sys.argv[1]

    print(f"Importing track metadata changes from: {csv_path}")

    # Import metadata updates
    tracks_updated, tracks_not_found, validation_errors, error_messages = (
        import_playlist_metadata_csv(Path(csv_path))
    )

    print("\n📊 Import Results:")
    print(f"   ✅ Tracks updated: {tracks_updated}")
    print(f"   ⚠️  Tracks not found: {tracks_not_found}")
    print(f"   ❌ Validation errors: {validation_errors}")

    if error_messages:
        print("\n⚠️  Errors encountered:")
        for error in error_messages[:10]:  # Show first 10 errors
            print(f"     • {error}")
        if len(error_messages) > 10:
            print(f"     ... and {len(error_messages) - 10} more errors")

    if tracks_updated > 0:
        print("\n✅ Metadata import completed successfully!")
        if tracks_not_found == 0 and validation_errors == 0:
            print("   All tracks were successfully updated.")
        else:
            print("   Some tracks had issues - check the errors above.")
    else:
        print("\n❌ No tracks were updated. Check the errors above.")


if __name__ == "__main__":
    main()
