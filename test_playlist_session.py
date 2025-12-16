#!/usr/bin/env python3
"""
Test script for playlist ranking session creation and resumption.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from music_minion.domain.rating.database import (
    get_playlist_ranking_session,
    create_playlist_ranking_session,
    delete_playlist_ranking_session,
)


def test_playlist_session_logic():
    """Test the playlist session creation/resumption logic."""

    playlist_id = 361

    print("=== Testing Playlist Session Logic ===")

    # Check existing session
    existing = get_playlist_ranking_session(playlist_id)
    print(f"Existing session: {existing is not None}")
    if existing:
        print(f"  Session ID: {existing['session_id']}")
        print(f"  Progress: {existing['progress_stats']}")

    # Simulate the web backend logic
    if existing:
        print("✅ Would resume existing session")
        session_id = existing["session_id"]
    else:
        print("✅ Would create new session")
        import uuid

        session_id = str(uuid.uuid4())
        try:
            create_playlist_ranking_session(playlist_id, session_id, 134)
            print("  New session created successfully")
        except Exception as e:
            print(f"  Failed to create session: {e}")

    print(f"Final session ID: {session_id}")


if __name__ == "__main__":
    test_playlist_session_logic()
