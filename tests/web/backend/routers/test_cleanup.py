"""Tag review router: every verdict path, DB refresh, and the ledger lock."""

import json
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mutagen.id3 import ID3, TIT2, TPE1, WOAF
from mutagen.mp4 import MP4

from music_minion.core.database import get_db_connection
from music_minion.domain.metadata_cleanup import apply as apply_mod
from music_minion.domain.metadata_cleanup import ingest, records
from music_minion.domain.metadata_cleanup.codex_runner import CodexSettings
from tests.domain.metadata_cleanup.test_m4a import (  # noqa: F401 (fixtures)
    MakeM4a,
    m4a_template,
    make_m4a,
    scdl_tags,
)
from web.backend.routers import cleanup as cleanup_router

MP3_ID = "2026/Oct 22/1. R - Song (R FLIP).mp3"
M4A_ID = "2026/Oct 22/2. U - Other (U VIP).m4a"
MP3_URL, M4A_URL = "https://soundcloud.com/r/song", "https://soundcloud.com/u/other"


def _proposal(track_id: str, artists: list[str], notes: str = "") -> dict:
    return {
        "id": track_id, "base_title": "Song", "artists": artists, "featured": [],
        "remixers": ["R"], "version": "Flip", "confidence": 0.8, "notes": notes,
    }  # fmt: skip


def _record(track_id: str) -> dict:
    sc = {"title": "Song (R FLIP)", "uploader": "R", "description": "free dl"}
    return {"id": track_id, "filename": "Song", "soundcloud": sc, "file_tags": {}}


def _pending(track_id: str) -> dict:
    return ingest._entry(
        "pending", track_id, record=_record(track_id),
        a=_proposal(track_id, ["Artist A"]), b=_proposal(track_id, ["Artist B"]),
    )  # fmt: skip


def _mp3(path: Path, title: str, url: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tags = ID3()
    tags.add(TIT2(encoding=3, text=[title]))
    tags.add(TPE1(encoding=3, text=["R"]))
    tags.add(WOAF(url=url))
    tags.save(path)
    return path


@pytest.fixture
def library(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    make_m4a: MakeM4a,  # noqa: F811 (fixture imported from test_m4a)
) -> Path:
    """Temp EDM root with one pending mp3 and one pending m4a in the ledger."""
    root = tmp_path / "EDM"
    monkeypatch.setattr(records, "MUSIC_ROOT", root)
    monkeypatch.setattr(ingest, "LEDGER_PATH", tmp_path / "work" / "ledger.json")
    monkeypatch.setattr(ingest, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(apply_mod, "BACKUPS_DIR", tmp_path / "backups")
    _mp3(root / MP3_ID, "Song (R FLIP)", MP3_URL)
    make_m4a(root / M4A_ID, scdl_tags("Other (U VIP)", M4A_URL))
    ingest.save_ledger({
        MP3_URL: _pending(MP3_ID),
        M4A_URL: _pending(M4A_ID),
        "https://soundcloud.com/old": ingest._entry("applied", "2025/old.mp3"),
    })  # fmt: skip
    return root


@pytest.fixture
def client(library: Path) -> TestClient:
    app = FastAPI()
    app.include_router(cleanup_router.router)
    return TestClient(app)


def _insert_track(path: Path) -> int:
    with get_db_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO tracks (local_path, title, artist, remix_artist)"
            " VALUES (?, 'Song (R FLIP)', 'R', 'Stale')",
            (str(path),),
        )
        conn.commit()
        return cursor.lastrowid


def _db_row(track_id: int) -> dict:
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT title, artist, remix_artist, file_mtime FROM tracks WHERE id = ?",
            (track_id,),
        ).fetchone()
    return dict(row)


def _decide(client: TestClient, track_id: str, verdict: str, **extra: object):
    return client.post(
        "/api/cleanup/pending/decision",
        json={"id": track_id, "verdict": verdict, **extra},
    )


def _status(url: str) -> str:
    return ingest.load_ledger()[url]["status"]


def test_pending_rows_include_db_track_id_and_context(
    client: TestClient, library: Path
) -> None:
    db_id = _insert_track(library / MP3_ID)

    body = client.get("/api/cleanup/pending").json()

    assert body["count"] == 2
    by_id = {row["id"]: row for row in body["rows"]}
    assert by_id[MP3_ID]["track_id"] == db_id
    assert by_id[M4A_ID]["track_id"] is None
    row = by_id[MP3_ID]
    assert row["current"]["title"] == "Song (R FLIP)"
    assert row["a"]["credited_artists"] == ["Artist A"]
    assert row["b"]["credited_artists"] == ["Artist B"]
    assert row["diff"]["credited_artists"] is True
    assert row["raw"]["url"] == MP3_URL and row["raw"]["description"] == "free dl"
    assert client.get("/api/cleanup/pending/count").json() == {"count": 2}


def test_model_verdict_writes_run_a_and_refreshes_the_db_row(
    client: TestClient, library: Path
) -> None:
    db_id = _insert_track(library / MP3_ID)

    response = _decide(client, MP3_ID, "model")

    assert response.status_code == 200
    assert response.json() == {
        "id": MP3_ID, "status": "applied", "written": True, "verdict": "model",
        "db_refreshed": True, "track_id": db_id, "remaining": 1,
    }  # fmt: skip
    tags = ID3(library / MP3_ID)
    assert (str(tags["TIT2"]), str(tags["TPE1"]), str(tags["TPE4"])) == (
        "Song (R Flip)", "Artist A", "R",
    )  # fmt: skip
    assert _db_row(db_id)["title"] == "Song (R Flip)"
    assert _db_row(db_id)["artist"] == "Artist A"
    assert _db_row(db_id)["remix_artist"] == "R"
    assert _db_row(db_id)["file_mtime"] == pytest.approx(
        (library / MP3_ID).stat().st_mtime
    )
    assert _status(MP3_URL) == "applied"
    assert ingest.load_ledger()[MP3_URL]["verdict"] == "model"
    logs = list(apply_mod.BACKUPS_DIR.glob("*/changes.jsonl"))
    assert len(logs) == 1 and json.loads(logs[0].read_text())["old"]["artist"] == "R"


def test_alt_verdict_writes_run_b_to_m4a(client: TestClient, library: Path) -> None:
    response = _decide(client, M4A_ID, "alt")

    assert response.json()["status"] == "applied"
    assert response.json()["db_refreshed"] is False  # no tracks row yet
    tags = MP4(library / M4A_ID).tags
    assert tags["©nam"] == ["Song (R Flip)"] and tags["©ART"] == ["Artist B"]
    assert "covr" in tags  # other atoms preserved
    assert _status(M4A_URL) == "applied"


def test_edited_verdict_writes_the_submitted_tags(
    client: TestClient, library: Path
) -> None:
    expected = {
        "title": " Song (R Edit) ", "credited_artists": ["X", " ", "Y"], "remixers": [],
    }  # fmt: skip
    response = _decide(client, MP3_ID, "edited", expected=expected)

    assert response.json()["status"] == "applied"
    tags = ID3(library / MP3_ID)
    assert str(tags["TIT2"]) == "Song (R Edit)" and str(tags["TPE1"]) == "X; Y"
    assert "TPE4" not in tags


def test_edited_without_tags_is_rejected(client: TestClient) -> None:
    assert _decide(client, MP3_ID, "edited").status_code == 422
    assert _decide(client, MP3_ID, "bogus").status_code == 422
    assert _status(MP3_URL) == "pending"


@pytest.mark.parametrize("verdict", ["gold", "exclude"])
def test_keep_and_skip_leave_the_file_alone(
    client: TestClient, library: Path, verdict: str
) -> None:
    before = (library / MP3_ID).read_bytes()

    response = _decide(client, MP3_ID, verdict)

    assert response.json()["status"] == "kept"
    assert response.json()["written"] is False
    assert (library / MP3_ID).read_bytes() == before
    assert _status(MP3_URL) == "kept"
    assert not apply_mod.BACKUPS_DIR.exists()


def test_unclear_stays_pending_and_sorts_last(
    client: TestClient, library: Path
) -> None:
    before = (library / MP3_ID).read_bytes()

    response = _decide(client, MP3_ID, "unclear")

    assert response.json()["status"] == "pending"
    assert response.json()["remaining"] == 2
    assert (library / MP3_ID).read_bytes() == before
    assert _status(MP3_URL) == "pending"
    rows = client.get("/api/cleanup/pending").json()["rows"]
    assert [(r["id"], r["unclear"]) for r in rows] == [(M4A_ID, False), (MP3_ID, True)]
    assert _decide(client, MP3_ID, "model").json()["status"] == "applied"


def test_resolved_or_unknown_track_is_404(client: TestClient) -> None:
    assert _decide(client, MP3_ID, "gold").status_code == 200
    again = _decide(client, MP3_ID, "model")
    assert again.status_code == 404 and MP3_ID in again.json()["detail"]
    assert _decide(client, "2026/nope.mp3", "model").status_code == 404


def test_tag_write_failure_keeps_entry_pending(
    client: TestClient, library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_write(path: Path, values: dict) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(apply_mod, "write_tags", broken_write)

    response = _decide(client, MP3_ID, "model")

    assert response.status_code == 500 and MP3_ID in response.json()["detail"]
    assert _status(MP3_URL) == "pending"


def test_missing_file_is_skipped_in_rows(client: TestClient, library: Path) -> None:
    (library / M4A_ID).unlink()
    rows = client.get("/api/cleanup/pending").json()["rows"]
    assert [row["id"] for row in rows] == [MP3_ID]


# --- ledger lock -----------------------------------------------------------


def test_entry_written_between_load_and_save_is_not_lost(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A writer slipping in between the decision's load and save survives."""
    real_apply = apply_mod.apply_changes

    def apply_then_ingest_writes(changes: list) -> tuple:
        ledger = ingest.load_ledger()
        ledger["https://soundcloud.com/new"] = _pending("2026/new.mp3")
        ingest.save_ledger(ledger)  # e.g. an ingest that ignores the lock
        return real_apply(changes)

    monkeypatch.setattr(apply_mod, "apply_changes", apply_then_ingest_writes)

    assert _decide(client, MP3_ID, "model").json()["status"] == "applied"

    ledger = ingest.load_ledger()
    assert ledger["https://soundcloud.com/new"]["status"] == "pending"
    assert ledger[MP3_URL]["status"] == "applied"


def test_ingest_merge_keeps_a_decision_made_while_codex_ran(
    library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex runs unlocked; a web decision meanwhile must not be reverted."""
    new_id = "2026/Oct 22/3. N - New.mp3"
    _mp3(library / new_id, "New", "https://soundcloud.com/n/new")
    monkeypatch.setattr(ingest, "raw_records", lambda scanned: [
        {"id": records.track_id(p), "filename": p.stem, "soundcloud": None, "file_tags": t}
        for p, t in scanned
    ])  # fmt: skip

    def codex(rows: list, settings: CodexSettings) -> tuple:
        with ingest.ledger_lock(timeout=0):  # proves ingest isn't holding it
            pass
        if ingest.load_ledger()[MP3_URL]["status"] == "pending":
            ingest.decide_pending(MP3_ID, {"verdict": "gold", "expected": None})
        return [_proposal(new_id, ["N"], "Assuming N")], []

    monkeypatch.setattr(ingest, "clean_rows", codex)

    assert ingest.run_ingest("2026", CodexSettings(), None)["pending"] == 1

    ledger = ingest.load_ledger()
    assert ledger[MP3_URL]["status"] == "kept"
    assert ledger["https://soundcloud.com/n/new"]["status"] == "pending"
    assert ledger[M4A_URL]["status"] == "pending"


def test_lock_times_out_while_another_holder_has_it(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ingest, "LOCK_TIMEOUT_S", 0.1)
    with ingest.ledger_lock():
        with pytest.raises(ingest.LedgerBusyError), ingest.ledger_lock():
            pass
        response = _decide(client, MP3_ID, "model")
    assert response.status_code == 503
    assert _status(MP3_URL) == "pending"
    assert _decide(client, MP3_ID, "model").status_code == 200  # released


def test_decision_waits_for_a_short_lock_holder(client: TestClient) -> None:
    held, release = threading.Event(), threading.Event()

    def holder() -> None:
        with ingest.ledger_lock():
            held.set()
            release.wait(timeout=5)

    thread = threading.Thread(target=holder)
    thread.start()
    held.wait(timeout=5)
    threading.Timer(0.2, release.set).start()
    started = time.monotonic()

    response = _decide(client, MP3_ID, "model")

    thread.join()
    assert response.status_code == 200
    assert time.monotonic() - started >= 0.15


def test_cli_resolve_pending_still_works(
    library: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    decisions = tmp_path / "decisions.json"
    decisions.write_text(json.dumps({
        MP3_ID: {"verdict": "alt", "expected": None},
        M4A_ID: {"verdict": "unclear", "expected": None},
    }))  # fmt: skip
    monkeypatch.setattr(ingest, "PENDING_DECISIONS_PATH", decisions)

    result = ingest.resolve_pending(write=True, sync_url=None)

    assert result == {"changes": 1, "resolved": 1, "written": 1}
    assert str(ID3(library / MP3_ID)["TPE1"]) == "Artist B"
    assert _status(MP3_URL) == "applied" and _status(M4A_URL) == "pending"
