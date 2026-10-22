"""Tests for the sync router's file-export gate."""

from dataclasses import replace

import pytest

from music_minion.core.config import Config, SyncConfig
from web.backend.routers import sync as sync_router


@pytest.fixture
def export_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    def fake_export(name: str):
        def run(show_progress: bool = True) -> dict[str, int]:
            calls.append(name)
            return {"success": 0}

        return run

    monkeypatch.setattr(
        sync_router.sync, "sync_metadata_export", fake_export("metadata")
    )
    monkeypatch.setattr(sync_router.sync, "sync_elo_export", fake_export("elo"))
    return calls


def _config(write_to_files: bool) -> Config:
    return replace(Config(), sync=SyncConfig(write_tags_to_metadata=write_to_files))


def test_file_exports_skipped_when_disabled(export_calls: list[str]) -> None:
    sync_router._export_to_files(_config(write_to_files=False))

    assert export_calls == []


def test_file_exports_run_when_enabled(export_calls: list[str]) -> None:
    sync_router._export_to_files(_config(write_to_files=True))

    assert export_calls == ["metadata", "elo"]


def test_file_exports_default_off() -> None:
    assert Config().sync.write_tags_to_metadata is False


@pytest.fixture
def quiet_sync(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Stub every sync phase; record smart playlist refreshes."""
    from music_minion.core import database
    from music_minion.domain.library import scanner
    from music_minion.domain.playlists import filters

    refreshes: list[str] = []
    monkeypatch.setattr(sync_router.config, "load_config", lambda: Config())
    monkeypatch.setattr(scanner, "scan_music_library_optimized", lambda *a, **k: [])
    monkeypatch.setattr(database, "batch_upsert_tracks", lambda tracks: (0, 0))
    monkeypatch.setattr(sync_router.sync, "detect_file_changes", lambda cfg: [])
    monkeypatch.setattr(sync_router.sync, "sync_import", lambda *a, **k: {"added": 0})
    monkeypatch.setattr(
        sync_router.sync,
        "detect_missing_and_moved_files",
        lambda cfg: {"relocated": 0, "deleted": 0},
    )
    monkeypatch.setattr(
        filters, "refresh_all_smart_playlists", lambda: refreshes.append("x") or 1
    )
    return refreshes


def test_incremental_sync_refreshes_smart_playlists(quiet_sync: list[str]) -> None:
    sync_router._run_sync()

    assert quiet_sync == ["x"]


def test_full_sync_refreshes_smart_playlists(quiet_sync: list[str]) -> None:
    sync_router._run_full_sync()

    assert quiet_sync == ["x"]
