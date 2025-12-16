#!/usr/bin/env python3
"""
Debug script to test playlist import path resolution.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from music_minion.domain.playlists.importers import resolve_relative_path


def test_path_resolution():
    # Test the path resolution logic
    from music_minion.core import config

    current_config = config.load_config()
    library_root = Path(current_config.music.library_paths[0]).expanduser()

    playlist_path = Path("/home/kevin/coding/music-minion-cli/NYE 25_fixed.m3u8")
    track_path = "2025/Jun 25/Jun 25_Omen.mp3"

    resolved = resolve_relative_path(playlist_path, track_path, library_root)
    print(f"Config library_paths[0]: {current_config.music.library_paths[0]}")
    print(f"Library root: {library_root}")
    print(f"Playlist path: {playlist_path}")
    print(f"Track path: {track_path}")
    print(f"Resolved path: {resolved}")
    print(f"Resolved path exists: {resolved.exists() if resolved else False}")

    # Test the expected path
    expected = library_root / track_path
    print(f"Expected path: {expected}")
    print(f"Expected exists: {expected.exists()}")


if __name__ == "__main__":
    test_path_resolution()
