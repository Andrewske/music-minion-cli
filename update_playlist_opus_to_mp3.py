#!/usr/bin/env python3
"""
Update playlist to reference MP3 files instead of deleted opus files.

After converting opus → MP3, this updates the playlist to point to the new MP3 tracks.
"""

import sys
from pathlib import Path

from music_minion.core.database import get_db_connection
from music_minion.domain.playlists.crud import get_playlist_by_name, get_playlist_tracks


def update_playlist_opus_to_mp3(playlist_name: str):
    """Update playlist tracks from .opus to .mp3 file references."""

    pl = get_playlist_by_name(playlist_name)
    if not pl:
        print(f"Error: Playlist '{playlist_name}' not found")
        return False

    tracks = get_playlist_tracks(pl["id"])
    print(f"Playlist '{playlist_name}' has {len(tracks)} tracks")

    # Find tracks that reference .opus files (which are now deleted)
    opus_tracks = [t for t in tracks if Path(t["local_path"]).suffix.lower() == ".opus"]
    print(f"Found {len(opus_tracks)} tracks with .opus extensions")

    if not opus_tracks:
        print("No opus tracks to update!")
        return True

    updated = 0
    not_found = 0

    with get_db_connection() as conn:
        for track in opus_tracks:
            old_path = track["local_path"]
            # Get the MP3 equivalent path
            mp3_path = str(Path(old_path).with_suffix(".mp3"))

            # Find the MP3 track in the database
            cursor = conn.execute(
                "SELECT id FROM tracks WHERE local_path = ?",
                (mp3_path,)
            )
            mp3_track = cursor.fetchone()

            if mp3_track:
                # Update playlist_tracks to reference the new MP3 track
                conn.execute(
                    """
                    UPDATE playlist_tracks
                    SET track_id = ?
                    WHERE playlist_id = ? AND track_id = ?
                    """,
                    (mp3_track["id"], pl["id"], track["id"])
                )
                updated += 1
                print(f"✓ Updated: {Path(old_path).name} → {Path(mp3_path).name}")
            else:
                not_found += 1
                print(f"✗ MP3 not found in database: {mp3_path}")
                print(f"  Run 'sync' first to add the MP3 files to the database")

        conn.commit()

    print(f"\n{'='*60}")
    print(f"Update complete:")
    print(f"  Updated:   {updated}")
    print(f"  Not found: {not_found}")
    print(f"  Total:     {len(opus_tracks)}")

    if not_found > 0:
        print(f"\nRun 'sync' to add the MP3 files to the database, then run this script again")
        return False

    return True


def main():
    playlist_name = sys.argv[1] if len(sys.argv) > 1 else "nye_25_final"

    print(f"Updating playlist '{playlist_name}' from opus to MP3...\n")

    success = update_playlist_opus_to_mp3(playlist_name)

    if success:
        print(f"\nPlaylist updated! Now run: playlist export {playlist_name} crate")
    else:
        print(f"\nFailed to update playlist")
        sys.exit(1)


if __name__ == "__main__":
    main()
