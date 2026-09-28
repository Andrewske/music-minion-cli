"""Manual feed sync must run off the request path (it takes most of an hour)."""

import threading

import pytest
from fastapi import HTTPException

from web.backend import sc_feed_worker


@pytest.fixture
def stub_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sc_feed_worker, "_mark_running", lambda: None)
    monkeypatch.setattr(
        sc_feed_worker, "get_sync_status", lambda: {"last_run_status": "running"}
    )


def test_manual_sync_returns_before_sync_finishes(
    stub_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = threading.Event()
    finished = threading.Event()

    def slow_sync(sweep: bool) -> dict:
        release.wait(timeout=5)
        finished.set()
        return {}

    monkeypatch.setattr(sc_feed_worker, "_fetch_feed_locked", slow_sync)

    result = sc_feed_worker.run_manual_sync()

    assert result == {"last_run_status": "running"}
    assert not finished.is_set()
    assert sc_feed_worker._feed_lock.locked()
    release.set()
    assert finished.wait(timeout=5)


def test_manual_sync_rejects_while_running(stub_db: None) -> None:
    assert sc_feed_worker._feed_lock.acquire(blocking=False)
    try:
        with pytest.raises(HTTPException) as exc_info:
            sc_feed_worker.run_manual_sync()
        assert exc_info.value.status_code == 429
    finally:
        sc_feed_worker._feed_lock.release()


def test_manual_sync_releases_lock_after_failure(
    stub_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    done = threading.Event()

    def failing_sync(sweep: bool) -> dict:
        done.set()
        raise RuntimeError("SC down")

    monkeypatch.setattr(sc_feed_worker, "_fetch_feed_locked", failing_sync)

    sc_feed_worker.run_manual_sync()

    assert done.wait(timeout=5)
    assert sc_feed_worker._feed_lock.acquire(timeout=5)
    sc_feed_worker._feed_lock.release()
