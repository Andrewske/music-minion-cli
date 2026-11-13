"""file_mtime bookkeeping after we write a tag ourselves."""

from music_minion.domain.sync.engine import mtime_after_own_write


def test_advances_when_file_was_in_sync() -> None:
    assert mtime_after_own_write(stored=100.0, before=100.0, after=105.0) == 105.0


def test_keeps_stored_when_file_changed_externally() -> None:
    assert mtime_after_own_write(stored=100.0, before=102.0, after=105.0) == 100.0


def test_never_synced_stays_unsynced() -> None:
    assert mtime_after_own_write(stored=None, before=100.0, after=105.0) is None
