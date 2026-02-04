"""Tests for YouTube import handlers."""

from dataclasses import FrozenInstanceError

import pytest

from music_minion.domain.library.providers.youtube.import_handlers import ImportResult


class TestImportResult:
    """Tests for ImportResult dataclass."""

    def test_import_result_creation(self) -> None:
        """ImportResult can be created with all fields."""
        result = ImportResult(
            tracks=[],
            imported_count=5,
            skipped_count=2,
            failed_count=1,
            failures=[("abc123", "Age restricted")],
        )

        assert result.imported_count == 5
        assert result.skipped_count == 2
        assert result.failed_count == 1
        assert len(result.failures) == 1
        assert result.failures[0] == ("abc123", "Age restricted")

    def test_import_result_is_frozen(self) -> None:
        """ImportResult is immutable (frozen dataclass)."""
        result = ImportResult(
            tracks=[],
            imported_count=0,
            skipped_count=0,
            failed_count=0,
            failures=[],
        )

        with pytest.raises(FrozenInstanceError):
            result.imported_count = 10  # type: ignore

    def test_import_result_empty_failures(self) -> None:
        """ImportResult works with empty failures list."""
        result = ImportResult(
            tracks=[],
            imported_count=10,
            skipped_count=0,
            failed_count=0,
            failures=[],
        )

        assert result.failures == []
        assert result.failed_count == 0
