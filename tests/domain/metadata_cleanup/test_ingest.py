from pathlib import Path

import pytest
from mutagen.id3 import ID3, TIT2, TPE1, WOAF

from music_minion.domain.metadata_cleanup import __main__ as cli
from music_minion.domain.metadata_cleanup import apply as apply_mod
from music_minion.domain.metadata_cleanup import ingest, plan, records
from music_minion.domain.metadata_cleanup.codex_runner import CodexSettings


def _proposal(track_id: str, artists: list[str], notes: str = "") -> dict:
    return {
        "id": track_id, "base_title": "Song", "artists": artists, "featured": [],
        "remixers": ["R"], "version": "Flip", "confidence": 0.9, "notes": notes,
    }  # fmt: skip


def _mp3(path: Path, title: str, url: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tags = ID3()
    tags.add(TIT2(encoding=3, text=[title]))
    tags.add(TPE1(encoding=3, text=["R"]))
    tags.add(WOAF(url=url))
    tags.save(path)


@pytest.fixture
def library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "EDM"
    monkeypatch.setattr(records, "MUSIC_ROOT", root)
    monkeypatch.setattr(ingest, "LEDGER_PATH", tmp_path / "ledger.json")
    monkeypatch.setattr(ingest, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(apply_mod, "BACKUPS_DIR", tmp_path / "backups")
    monkeypatch.setattr(ingest, "raw_records", lambda scanned: [
        {"id": records.track_id(p), "filename": p.stem, "soundcloud": None, "file_tags": t}
        for p, t in scanned
    ])  # fmt: skip
    return root


def test_ledger_key_prefers_soundcloud_url() -> None:
    assert (
        ingest.ledger_key("a/b.mp3", {"source_url": "https://sc/x"}) == "https://sc/x"
    )
    assert ingest.ledger_key("a/b.mp3", {}) == "a/b.mp3"


def test_gate_sends_hedged_agreements_to_review() -> None:
    row = {"auto": True, "notes": "Assuming Evil Empire is the original artist"}
    assert plan.gate(row)["auto"] is False
    assert plan.gate({"auto": True, "notes": "Description confirms it"})["auto"] is True
    assert plan.is_hedged("Original artist not identified in the metadata")


def test_run_ingest_applies_agreed_and_queues_the_rest(
    library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mp3(
        library / "2026/Oct 26/1. R - Artist - Song (R FLIP).mp3",
        "Artist - Song (R FLIP)",
        "https://sc/1",
    )
    _mp3(
        library / "2026/Oct 26/2. R - Song (R FLIP).mp3",
        "Song (R FLIP)",
        "https://sc/2",
    )
    ok, hedged = (
        "2026/Oct 26/1. R - Artist - Song (R FLIP).mp3",
        "2026/Oct 26/2. R - Song (R FLIP).mp3",
    )
    answers = [
        _proposal(ok, ["Artist"]),
        _proposal(hedged, ["Guess"], "Assuming Guess"),
    ]
    monkeypatch.setattr(ingest, "clean_rows", lambda rows, settings: (answers, []))
    calls = []
    monkeypatch.setattr(ingest, "trigger_sync", lambda url: calls.append(url))

    summary = ingest.run_ingest("2026", CodexSettings(), "http://sync")

    assert summary == {
        "new": 2, "written": 1, "failed": 0, "pending": 1, "codex_missing": 0,
    }  # fmt: skip
    assert ingest.exit_code(summary) == 0
    tags = ID3(library / ok)
    assert (str(tags["TIT2"]), str(tags["TPE1"]), str(tags["TPE4"])) == (
        "Song (R Flip)",
        "Artist",
        "R",
    )
    assert str(ID3(library / hedged)["TIT2"]) == "Song (R FLIP)"  # untouched
    ledger = ingest.load_ledger()
    assert {k: v["status"] for k, v in ledger.items()} == {
        "https://sc/1": "applied",
        "https://sc/2": "pending",
    }
    assert calls == ["http://sync"]
    assert ingest.run_ingest("2026", CodexSettings(), None) == {"new": 0}


def test_bootstrap_marks_existing_files(library: Path) -> None:
    _mp3(library / "2026/Oct 26/a.mp3", "A", "https://sc/a")
    assert ingest.bootstrap("2026") == 1
    assert ingest.load_ledger()["https://sc/a"]["status"] == "baseline"


def test_resolve_pending_writes_decided_tracks(
    library: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    track_id = "2026/Oct 26/x.mp3"
    _mp3(library / track_id, "RAW", "https://sc/x")
    record = {"id": track_id, "filename": "x", "soundcloud": None, "file_tags": {}}
    ingest.save_ledger({"https://sc/x": ingest._entry(
        "pending", track_id, record=record,
        a=_proposal(track_id, ["A"]), b=_proposal(track_id, ["B"]),
    )})  # fmt: skip
    decisions = tmp_path / "decisions.json"
    decisions.write_text('{"%s": {"verdict": "alt", "expected": null}}' % track_id)
    monkeypatch.setattr(ingest, "PENDING_DECISIONS_PATH", decisions)

    assert ingest.resolve_pending(write=False, sync_url=None)["written"] == 0
    assert str(ID3(library / track_id)["TPE1"]) == "R"
    result = ingest.resolve_pending(write=True, sync_url=None)
    assert result == {"changes": 1, "resolved": 1, "written": 1}
    assert str(ID3(library / track_id)["TPE1"]) == "B"
    assert ingest.load_ledger()["https://sc/x"]["status"] == "applied"


def test_failed_codex_batches_are_counted_and_exit_nonzero(
    library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for n in range(3):
        _mp3(library / f"2026/Oct 26/{n}.mp3", f"T{n}", f"https://sc/{n}")
    monkeypatch.setattr(ingest, "clean_rows", lambda rows, settings: ([], []))

    summary = ingest.run_ingest("2026", CodexSettings(), None)

    assert summary == {
        "new": 3, "written": 0, "failed": 0, "pending": 0, "codex_missing": 3,
    }  # fmt: skip
    assert ingest.exit_code(summary) == 1
    assert ingest.load_ledger() == {}  # all three stay "new" for the next run


def test_ingest_cli_exits_nonzero_when_codex_returns_nothing(
    library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mp3(library / "2026/Oct 26/x.mp3", "T", "https://sc/x")
    monkeypatch.setattr(ingest, "clean_rows", lambda rows, settings: ([], []))

    assert cli.main(["ingest", "--year", "2026", "--no-sync"]) == 1


def test_one_run_missing_a_track_counts_it(
    library: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    track_id = "2026/Oct 26/x.mp3"
    _mp3(library / track_id, "T", "https://sc/x")
    runs = iter([[_proposal(track_id, ["A"])], []])  # run a answers, run b fails
    monkeypatch.setattr(ingest, "clean_rows", lambda rows, s: (next(runs), []))

    assert ingest.run_ingest("2026", CodexSettings(), None)["codex_missing"] == 1


def test_exit_code_flags_write_failures_and_ignores_empty_runs(
    library: Path,
) -> None:
    assert ingest.exit_code({"new": 0}) == 0
    assert ingest.exit_code({"failed": 1, "codex_missing": 0}) == 1
    assert cli.main(["ingest", "--year", "2026", "--no-sync"]) == 0  # nothing new
