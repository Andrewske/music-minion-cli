"""Full local sync runs every phase, through the missing/moved-file cleanup.

A crash in an earlier phase (a query on the dropped elo_ratings table) hid
the cleanup for months, so this pins the phase order with the I/O stubbed.
"""

import pytest

from music_minion import helpers
from music_minion.commands import sync as sync_command
from music_minion.context import AppContext
from music_minion.core import database
from music_minion.core.config import Config
from music_minion.domain.library import scanner


@pytest.fixture
def phases(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def record(name: str, result: object):
        def run(*_args: object, **_kwargs: object) -> object:
            calls.append(name)
            return result

        return run

    monkeypatch.setattr(scanner, "scan_music_library_optimized", record("scan", []))
    monkeypatch.setattr(database, "batch_upsert_tracks", record("upsert", (0, 0)))
    monkeypatch.setattr(
        sync_command.sync, "sync_metadata_export", record("export", {"success": 0})
    )
    monkeypatch.setattr(
        sync_command.sync,
        "detect_missing_and_moved_files",
        record("cleanup", {"relocated": 0, "deleted": 0}),
    )
    monkeypatch.setattr(
        helpers, "reload_tracks", lambda ctx: calls.append("reload") or ctx
    )
    monkeypatch.setattr(sync_command, "log", lambda *_a, **_k: None)
    return calls


def test_full_sync_reaches_cleanup_and_reload(phases: list[str]) -> None:
    ctx = AppContext.create(Config())

    _, keep_going = sync_command._sync_local_full(ctx)

    assert keep_going is True
    assert phases == ["scan", "export", "cleanup", "reload"]
