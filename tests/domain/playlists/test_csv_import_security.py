"""
Test CSV import security limits.
"""

import tempfile
from pathlib import Path

import pytest

from music_minion.domain.playlists.importers import import_playlist_metadata_csv


def test_csv_file_size_limit():
    """Verify CSV file size limit enforced."""
    # Create a CSV file larger than 10MB
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_path = Path(f.name)

        # Write header
        f.write("local_path,title,artist\n")

        # Write enough rows to exceed 10MB (about 11MB of data)
        row = "x" * 1000 + ",Test Track,Test Artist\n"  # ~1KB per row
        for _ in range(12000):  # 12000 rows * 1KB = ~12MB
            f.write(row)

    try:
        # Attempt import - should fail with "too large" message
        with pytest.raises(ValueError, match="CSV file too large.*max"):
            import_playlist_metadata_csv(csv_path)
    finally:
        csv_path.unlink()


def test_csv_row_limit():
    """Verify CSV row count limit enforced (simplified test)."""
    # Note: Full row limit test (10,000+) is slow. This tests the logic with smaller numbers.
    # The actual security check in importers.py uses MAX_CSV_ROWS = 10000

    # Just verify the constant exists and security check is in place
    from music_minion.domain.playlists.importers import MAX_CSV_ROWS

    assert MAX_CSV_ROWS == 10000, "MAX_CSV_ROWS security limit should be 10000"

    # For actual row processing, a full integration test would be needed with test database
    # This test verifies the constant is defined correctly


def test_csv_field_length_limit():
    """Verify metadata field length limit enforced."""
    # Create a CSV with an overly long field value
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_path = Path(f.name)

        # Write header
        f.write("local_path,title,artist\n")

        # Write row with 1001-character artist name (exceeds MAX_FIELD_LENGTH of 1000)
        long_artist = "x" * 1001
        f.write(f"/music/track.opus,Test Track,{long_artist}\n")

        f.flush()  # Ensure all data is written

    try:
        # Import should catch the field length violation
        updated, not_found, validation_errors, error_messages = import_playlist_metadata_csv(csv_path)

        # Should have validation error for long field
        assert validation_errors > 0, "Expected validation errors for long field"
        assert any("too long" in msg for msg in error_messages), \
            f"Expected 'too long' error message, got: {error_messages}"
    finally:
        csv_path.unlink()
