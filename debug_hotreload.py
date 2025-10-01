#!/usr/bin/env python3
"""Debug hot-reload to see if files are being watched."""

import time
import sys
from pathlib import Path

sys.path.insert(0, 'src')

from music_minion import dev_reload

def test_watcher():
    """Test if file watcher is working."""
    print("🔍 Testing hot-reload file watcher")
    print("=" * 50)

    # Track what gets detected
    detected_files = []

    def on_change(filepath):
        print(f"✅ Detected change: {filepath}")
        detected_files.append(filepath)

    # Setup watcher
    result = dev_reload.setup_file_watcher(on_change)

    if not result:
        print("❌ Failed to setup watcher")
        return False

    observer, handler = result
    print(f"✅ Watcher started")
    print(f"   Watching: {Path('src/music_minion').resolve()}")
    print("\nNow edit a file in src/music_minion/ and save it...")
    print("Press Ctrl+C to stop\n")

    try:
        while True:
            # Check for pending changes
            ready = handler.check_pending_changes()
            if ready:
                print(f"📦 Ready to reload: {ready}")

            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n\nStopping...")

    dev_reload.stop_file_watcher(observer)

    print(f"\n📊 Summary:")
    print(f"   Files detected: {len(detected_files)}")
    for f in detected_files:
        print(f"   - {f}")

    return len(detected_files) > 0

if __name__ == "__main__":
    success = test_watcher()
    sys.exit(0 if success else 1)
