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
