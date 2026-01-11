#!/usr/bin/env python3
"""
Convert opus files in playlist to MP3 format.

Preserves all metadata and replaces .opus files with .mp3 versions.
"""

import subprocess
import sys
from pathlib import Path

from music_minion.domain.playlists.crud import get_playlist_by_name, get_playlist_tracks


def convert_opus_to_mp3(opus_path: Path) -> tuple[bool, str]:
    """
    Convert an opus file to MP3 using ffmpeg.

    Args:
        opus_path: Path to the .opus file

    Returns:
        Tuple of (success: bool, message: str)
    """
    if not opus_path.exists():
        return False, f"File not found: {opus_path}"

    # Output path: same name but .mp3 extension
    mp3_path = opus_path.with_suffix(".mp3")

    # Don't overwrite existing MP3
    if mp3_path.exists():
        return False, f"MP3 already exists: {mp3_path}"

    # Convert using ffmpeg with high quality settings
    # -q:a 0 = highest quality VBR MP3 (equivalent to V0)
    cmd = [
        "ffmpeg",
        "-i",
        str(opus_path),
        "-q:a",
        "0",  # Highest quality VBR
        "-map_metadata",
        "0",  # Copy all metadata
        "-id3v2_version",
        "3",  # Use ID3v2.3 for better compatibility
        str(mp3_path),
        "-y",  # Overwrite without asking
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=60
        )
        # Delete original opus file after successful conversion
        opus_path.unlink()
        return True, f"Converted: {opus_path.name} -> {mp3_path.name}"
    except subprocess.CalledProcessError as e:
        return False, f"ffmpeg error: {e.stderr}"
    except subprocess.TimeoutExpired:
        return False, "Conversion timed out (>60s)"
    except Exception as e:
        return False, f"Error: {e}"


def main():
    playlist_name = sys.argv[1] if len(sys.argv) > 1 else "nye_25_final"

    print(f"Converting opus files in playlist: {playlist_name}\n")

    # Get playlist
    pl = get_playlist_by_name(playlist_name)
    if not pl:
        print(f"Error: Playlist '{playlist_name}' not found")
        sys.exit(1)

    # Get tracks
    tracks = get_playlist_tracks(pl["id"])

    # Filter opus files
    opus_tracks = [t for t in tracks if Path(t["local_path"]).suffix.lower() == ".opus"]

    print(f"Found {len(opus_tracks)} opus files to convert\n")

    if not opus_tracks:
        print("No opus files to convert!")
        sys.exit(0)

    # Check if ffmpeg is available
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: ffmpeg is not installed")
        print("Install with: sudo pacman -S ffmpeg")
        sys.exit(1)

    # Convert each file
    success_count = 0
    failed_count = 0

    for idx, track in enumerate(opus_tracks, 1):
        opus_path = Path(track["local_path"])
        print(f"[{idx}/{len(opus_tracks)}] {opus_path.name}...", end=" ")

        success, message = convert_opus_to_mp3(opus_path)

        if success:
            print(f"✓ {message}")
            success_count += 1
        else:
            print(f"✗ {message}")
            failed_count += 1

    # Summary
    print(f"\n{'='*60}")
    print(f"Conversion complete:")
    print(f"  Success: {success_count}")
    print(f"  Failed:  {failed_count}")
    print(f"  Total:   {len(opus_tracks)}")

    if success_count > 0:
        print(f"\nNext steps:")
        print(f"1. Run 'sync incremental' to update database with new MP3 files")
        print(f"2. Re-export playlist: 'playlist export {playlist_name} crate'")


if __name__ == "__main__":
    main()
