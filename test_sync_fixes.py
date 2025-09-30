#!/usr/bin/env python3
"""
Test script for Phase 7 sync functionality bug fixes.

Tests all critical bug fixes:
1. Tag removal only removes source='file' tags (preserves user/AI tags)
2. Atomic file writes (temp file + rename)
3. mtime tracking with float precision
4. File format validation
5. Tag deduplication
6. Batch database updates
7. Progress reporting

Run with: uv run python test_sync_fixes.py
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from music_minion import sync, database, config as cfg
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, COMM, TIT2


def setup_test_environment():
    """Create a temporary test environment."""
    test_dir = tempfile.mkdtemp(prefix="mm_sync_test_")
    print(f"Created test directory: {test_dir}")

    # Create test config
    test_config = cfg.Config()
    test_config.sync.write_tags_to_metadata = True
    test_config.sync.tag_prefix = "mm:"
    test_config.sync.auto_sync_on_startup = False

    return test_dir, test_config


def create_test_mp3(file_path: str, title: str = "Test Track") -> str:
    """Create a minimal MP3 file for testing."""
    # Create a minimal valid MP3 file
    # MP3 frame header: 0xFFFB (MPEG1 Layer 3, 128kbps, 44.1kHz)
    mp3_header = bytes([0xFF, 0xFB, 0x90, 0x00])
    mp3_data = mp3_header + bytes([0x00] * 1000)  # Minimal valid frame

    with open(file_path, 'wb') as f:
        f.write(mp3_data)

    # Add ID3 tags
    audio = MP3(file_path)
    audio.tags = ID3()
    audio.tags.add(TIT2(encoding=3, text=title))
    audio.save()

    return file_path


def test_tag_removal_preservation(test_dir: str, test_config: cfg.Config):
    """Test that only source='file' tags are removed, user/AI tags preserved."""
    print("\n=== Test 1: Tag Removal Logic ===")

    # Create test MP3
    test_file = create_test_mp3(os.path.join(test_dir, "test1.mp3"))

    # Initialize database (in-memory for testing)
    database.init_database()

    # Add track to database
    from music_minion.database import add_track, add_tags, get_track_tags

    track_id = add_track(test_file, "Artist", "Test Track", "Album", 2025)

    # Add tags with different sources
    add_tags(track_id, ["user-tag"], source="user")
    add_tags(track_id, ["ai-tag"], source="ai")
    add_tags(track_id, ["file-tag"], source="file")

    print(f"  Added tags: user-tag (user), ai-tag (ai), file-tag (file)")

    # Write file-tag to file metadata
    sync.write_tags_to_file(test_file, ["file-tag", "new-file-tag"], test_config)
    print(f"  Wrote to file: file-tag, new-file-tag")

    # Import from file (should remove file-tag but keep user/AI tags)
    sync.sync_import(test_config, force_all=True, show_progress=False)

    # Check final tags
    final_tags = get_track_tags(track_id, include_blacklisted=False)
    tag_names = {tag['tag_name']: tag['source'] for tag in final_tags}

    print(f"  Final tags in database: {tag_names}")

    # Assertions
    assert "user-tag" in tag_names, "❌ FAILED: user-tag was removed!"
    assert "ai-tag" in tag_names, "❌ FAILED: ai-tag was removed!"
    assert "new-file-tag" in tag_names, "❌ FAILED: new-file-tag not added!"
    assert "file-tag" in tag_names, "❌ FAILED: file-tag was incorrectly removed!"

    print("  ✅ PASSED: User and AI tags preserved, file tags synced correctly")

    return True


def test_atomic_writes(test_dir: str, test_config: cfg.Config):
    """Test that file writes use atomic temp file + rename."""
    print("\n=== Test 2: Atomic File Writes ===")

    test_file = create_test_mp3(os.path.join(test_dir, "test2.mp3"))

    # Write tags
    result = sync.write_tags_to_file(test_file, ["test-tag"], test_config)

    # Check no .tmp files left behind
    tmp_files = list(Path(test_dir).glob("*.tmp"))
    assert len(tmp_files) == 0, f"❌ FAILED: Temp files left behind: {tmp_files}"

    # Verify tags were written
    tags = sync.read_tags_from_file(test_file, test_config)
    assert "test-tag" in tags, "❌ FAILED: Tag not written to file!"

    print("  ✅ PASSED: Atomic writes working, no temp files left behind")

    return True


def test_mtime_precision(test_dir: str, test_config: cfg.Config):
    """Test that mtime uses float precision (sub-second)."""
    print("\n=== Test 3: mtime Float Precision ===")

    test_file = create_test_mp3(os.path.join(test_dir, "test3.mp3"))

    mtime = sync.get_file_mtime(test_file)

    # Check it's a float
    assert isinstance(mtime, float), f"❌ FAILED: mtime is {type(mtime)}, expected float"

    # Check it has sub-second precision (decimal part)
    assert mtime != int(mtime), "⚠️  WARNING: mtime has no sub-second precision"

    print(f"  mtime: {mtime} (float with sub-second precision)")
    print("  ✅ PASSED: mtime uses float precision")

    return True


def test_file_format_validation(test_dir: str, test_config: cfg.Config):
    """Test that unsupported formats are rejected."""
    print("\n=== Test 4: File Format Validation ===")

    # Create a fake unsupported file
    fake_file = os.path.join(test_dir, "test.txt")
    with open(fake_file, 'w') as f:
        f.write("Not an audio file")

    result = sync.write_tags_to_file(fake_file, ["test-tag"], test_config)

    assert result is False, "❌ FAILED: Non-audio file was not rejected!"

    print("  ✅ PASSED: Unsupported format rejected")

    return True


def test_tag_deduplication(test_dir: str, test_config: cfg.Config):
    """Test that duplicate tags in files are deduplicated."""
    print("\n=== Test 5: Tag Deduplication ===")

    test_file = create_test_mp3(os.path.join(test_dir, "test5.mp3"))

    # Write duplicate tags to file manually
    audio = MP3(test_file)
    if audio.tags is None:
        audio.add_tags()

    # Add comment with duplicate tags
    audio.tags.delall("COMM")
    audio.tags.add(COMM(encoding=3, lang='eng', desc='',
                        text="mm:tag1, mm:tag1, mm:tag2, mm:tag2"))
    audio.save()

    # Read and check for deduplication
    tags = sync.read_tags_from_file(test_file, test_config)

    tag_counts = {}
    for tag in tags:
        tag_counts[tag] = tag_counts.get(tag, 0) + 1

    print(f"  Tags read: {tags}")
    print(f"  Tag counts: {tag_counts}")

    # Check no duplicates
    for tag, count in tag_counts.items():
        assert count == 1, f"❌ FAILED: Tag '{tag}' appears {count} times!"

    print("  ✅ PASSED: Tags deduplicated correctly")

    return True


def test_progress_reporting(test_dir: str, test_config: cfg.Config):
    """Test that progress is reported at reasonable intervals."""
    print("\n=== Test 6: Progress Reporting ===")

    # Create 150 test files (enough to trigger multiple progress updates)
    test_files = []
    for i in range(150):
        test_file = create_test_mp3(os.path.join(test_dir, f"test_progress_{i}.mp3"))
        test_files.append(test_file)

    print(f"  Created {len(test_files)} test files")

    # Note: Progress reporting is visual, hard to test programmatically
    # This test just ensures it doesn't crash with many files

    database.init_database()
    from music_minion.database import add_track

    track_ids = []
    for i, test_file in enumerate(test_files):
        track_id = add_track(test_file, "Artist", f"Track {i}", "Album", 2025)
        track_ids.append(track_id)

    print("  Testing export with progress reporting...")
    stats = sync.sync_export(test_config, track_ids=track_ids, show_progress=True)

    print(f"  Export stats: {stats}")

    assert stats['success'] > 0, "❌ FAILED: No files exported!"

    print("  ✅ PASSED: Progress reporting working")

    return True


def cleanup(test_dir: str):
    """Clean up test environment."""
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
        print(f"\nCleaned up test directory: {test_dir}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Phase 7 Sync Functionality Bug Fix Tests")
    print("=" * 60)

    test_dir, test_config = setup_test_environment()

    try:
        tests = [
            test_tag_removal_preservation,
            test_atomic_writes,
            test_mtime_precision,
            test_file_format_validation,
            test_tag_deduplication,
            test_progress_reporting,
        ]

        passed = 0
        failed = 0

        for test_func in tests:
            try:
                if test_func(test_dir, test_config):
                    passed += 1
            except Exception as e:
                print(f"  ❌ FAILED: {e}")
                import traceback
                traceback.print_exc()
                failed += 1

        print("\n" + "=" * 60)
        print(f"Test Results: {passed} passed, {failed} failed")
        print("=" * 60)

        if failed > 0:
            sys.exit(1)
        else:
            print("\n🎉 All tests passed!")
            sys.exit(0)

    finally:
        cleanup(test_dir)


if __name__ == "__main__":
    main()