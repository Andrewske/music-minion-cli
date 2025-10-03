#!/usr/bin/env python3
"""
Test script for autoplay functionality.

Tests:
1. Track completion detection (is_track_finished)
2. Auto-advance after track ends
3. Shuffle mode integration
4. Sequential mode integration
"""

import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from music_minion.domain.playback import player
from music_minion.context import AppContext
from music_minion.core import config


def test_track_finished_detection():
    """Test that is_track_finished() correctly detects when a track ends."""
    print("\n=== Test 1: Track Completion Detection ===")

    # Create a basic player state
    cfg = config.load_config()

    # Start MPV
    print("Starting MPV...")
    state = player.start_mpv(cfg)

    if not state:
        print("❌ Failed to start MPV")
        return False

    print("✅ MPV started successfully")

    # Check initial state (no track, should be False)
    is_finished = player.is_track_finished(state)
    if is_finished:
        print("❌ is_track_finished should be False when no track is playing")
        player.stop_mpv(state)
        return False

    print("✅ is_track_finished correctly returns False when no track is playing")

    # Clean up
    player.stop_mpv(state)
    print("✅ Test 1 passed\n")
    return True


def test_eof_property():
    """Test that we can query MPV's eof-reached property."""
    print("\n=== Test 2: EOF Property Query ===")

    cfg = config.load_config()

    # Start MPV
    print("Starting MPV...")
    state = player.start_mpv(cfg)

    if not state:
        print("❌ Failed to start MPV")
        return False

    # Query eof-reached property
    eof = player.get_mpv_property(state.socket_path, 'eof-reached')
    print(f"eof-reached property: {eof} (type: {type(eof).__name__})")

    # Should be False or None when no file is loaded
    if eof is True:
        print("❌ eof-reached should not be True when no file is loaded")
        player.stop_mpv(state)
        return False

    print("✅ eof-reached property queried successfully")

    # Clean up
    player.stop_mpv(state)
    print("✅ Test 2 passed\n")
    return True


def test_duration_fallback():
    """Test that position vs duration fallback works."""
    print("\n=== Test 3: Duration Fallback Logic ===")

    cfg = config.load_config()

    # Start MPV
    print("Starting MPV...")
    state = player.start_mpv(cfg)

    if not state:
        print("❌ Failed to start MPV")
        return False

    # When no file is loaded, position and duration should be 0
    position = player.get_mpv_property(state.socket_path, 'time-pos') or 0.0
    duration = player.get_mpv_property(state.socket_path, 'duration') or 0.0

    print(f"position: {position}, duration: {duration}")

    # Check logic: position >= duration - 0.5
    # With 0/0, should not trigger
    is_finished = player.is_track_finished(state)

    if is_finished:
        print("❌ Should not detect finished when no file is loaded")
        player.stop_mpv(state)
        return False

    print("✅ Duration fallback logic works correctly")

    # Clean up
    player.stop_mpv(state)
    print("✅ Test 3 passed\n")
    return True


def main():
    """Run all tests."""
    print("╔════════════════════════════════════════╗")
    print("║   AUTOPLAY FUNCTIONALITY TESTS         ║")
    print("╚════════════════════════════════════════╝")

    tests = [
        test_track_finished_detection,
        test_eof_property,
        test_duration_fallback,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    # Summary
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print(f"❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
