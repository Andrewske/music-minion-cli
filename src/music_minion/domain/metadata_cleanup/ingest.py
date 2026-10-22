"""Unattended cleanup of newly downloaded tracks (runs after the nightly scdl job).

New = an MP3 or M4A in the year folder whose SoundCloud URL (or path) is not in the
ledger. Each new track is cleaned twice; when both runs agree and neither
hedges, the tags are written. Everything else waits in the ledger as
"pending" for `review --mode pending` + `apply --pending --write`.
"""

import json
import os
from datetime import datetime
from typing import Any

import requests
from loguru import logger

from music_minion.domain.metadata_cleanup import apply as apply_mod
from music_minion.domain.metadata_cleanup import plan, records, review
from music_minion.domain.metadata_cleanup.codex_runner import CodexSettings
from music_minion.domain.metadata_cleanup.pipeline import (
    RUNS_DIR,
    Scanned,
    clean_rows,
    raw_records,
    scan,
)
from music_minion.domain.metadata_cleanup.render import DEFAULT_SEPARATORS

LEDGER_PATH = records.WORK_DIR / "ledger.json"
PENDING_DECISIONS_PATH = records.WORK_DIR / "apply-decisions-pending.json"
DEFAULT_SYNC_URL = "http://127.0.0.1:8642/api/sync"

Ledger = dict[str, dict[str, Any]]


def ledger_key(track_id: str, tags: dict[str, str]) -> str:
    """SoundCloud URL survives renames/moves; fall back to the path."""
    return tags.get("source_url") or track_id


def load_ledger() -> Ledger:
    return json.loads(LEDGER_PATH.read_text()) if LEDGER_PATH.exists() else {}


def save_ledger(ledger: Ledger) -> None:
    temp = LEDGER_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(ledger, indent=1, ensure_ascii=False))
    os.replace(temp, LEDGER_PATH)


def find_new(scanned: Scanned, ledger: Ledger) -> Scanned:
    return [
        (path, tags)
        for path, tags in scanned
        if ledger_key(records.track_id(path), tags) not in ledger
    ]


def _entry(status: str, track_id: str, **extra: Any) -> dict[str, Any]:
    return {"status": status, "id": track_id, "at": datetime.now().isoformat(), **extra}


def bootstrap(year: str) -> int:
    """Mark every current file as already handled so only future downloads run."""
    ledger = load_ledger()
    for path, tags in find_new(scan(records.MUSIC_ROOT / year), ledger):
        track_id = records.track_id(path)
        ledger[ledger_key(track_id, tags)] = _entry("baseline", track_id)
    save_ledger(ledger)
    return len(ledger)


def _two_runs(rows: list[dict], settings: CodexSettings) -> tuple[dict, dict]:
    run_dir = RUNS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-ingest"
    run_dir.mkdir(parents=True)
    records.write_jsonl(run_dir / "records.jsonl", rows)
    runs = []
    for label in ("a", "b"):
        proposals, _ = clean_rows(rows, settings)
        records.write_jsonl(run_dir / f"proposals-{label}.jsonl", proposals)
        runs.append({p["id"]: p for p in proposals})
    return runs[0], runs[1]


def _decide(
    rows: list[dict], tags_by_id: dict, a: dict, b: dict
) -> tuple[list, Ledger]:
    """Split into (changes to write now, ledger entries) for this batch."""
    changes, entries = [], {}
    for record in rows:
        track_id, tags = record["id"], tags_by_id[record["id"]]
        key = ledger_key(track_id, tags)
        if track_id not in a or track_id not in b:
            continue  # a failed batch: stays "new", retried next run
        row = plan.gate(plan.build_apply_row(record, tags, a[track_id], b[track_id]))
        if not row["auto"]:
            entries[key] = _entry(
                "pending", track_id, record=record, a=a[track_id], b=b[track_id]
            )
            continue
        current = apply_mod.read_current(records.MUSIC_ROOT / track_id)
        change = plan.build_change(track_id, current, row["a"], DEFAULT_SEPARATORS)
        changes += [change] if change else []
        entries[key] = _entry("applied" if change else "unchanged", track_id)
    return changes, entries


def trigger_sync(url: str) -> None:
    """Ask music-minion to re-import changed files; failure is not fatal."""
    try:
        requests.post(url, timeout=15).raise_for_status()
        logger.info(f"Triggered music-minion sync at {url}")
    except requests.RequestException:
        logger.exception(f"Could not trigger music-minion sync at {url}")


def count_codex_missing(rows: list[dict], a: dict, b: dict) -> int:
    """Tracks with no proposal from run a or run b (failed/mangled codex batch).

    They stay "new" and are retried next run, but must not pass silently.
    """
    return sum(1 for row in rows if row["id"] not in a or row["id"] not in b)


def exit_code(summary: dict[str, int]) -> int:
    """Non-zero when any track failed to write or got no codex answer."""
    return 1 if summary.get("codex_missing", 0) or summary.get("failed", 0) else 0


def run_ingest(year: str, settings: CodexSettings, sync_url: str | None) -> dict:
    ledger = load_ledger()
    new = find_new(scan(records.MUSIC_ROOT / year), ledger)
    if not new:
        logger.info(f"Metadata cleanup: no new tracks in {year}")
        return {"new": 0}
    rows = raw_records(new)
    tags_by_id = {records.track_id(path): tags for path, tags in new}
    a, b = _two_runs(rows, settings)
    changes, entries = _decide(rows, tags_by_id, a, b)
    backup, written, failed = (
        apply_mod.apply_changes(changes) if changes else (None, 0, [])
    )
    entries = {k: v for k, v in entries.items() if v["id"] not in failed}
    save_ledger({**ledger, **entries})
    if written and sync_url:
        trigger_sync(sync_url)
    summary = {
        "new": len(new),
        "written": written,
        "failed": len(failed),
        "pending": sum(1 for e in entries.values() if e["status"] == "pending"),
        "codex_missing": count_codex_missing(rows, a, b),
    }
    log_level = "ERROR" if exit_code(summary) else "INFO"
    logger.log(log_level, f"Metadata cleanup: {summary} backup={backup}")
    return summary


def pending_rows(ledger: Ledger) -> list[dict]:
    """Review rows for every pending track, with current tags read fresh."""
    rows = []
    for entry in ledger.values():
        if entry["status"] != "pending":
            continue
        tags = records.read_tags(records.MUSIC_ROOT / entry["id"])
        row = plan.build_apply_row(entry["record"], tags, entry["a"], entry["b"])
        raw = review.raw_view(entry["record"], tags.get("source_url"))
        rows.append({**row, "auto": False, "left": row["current"], "raw": raw})
    return rows


def resolve_pending(write: bool, sync_url: str | None) -> dict:
    """Apply reviewed pending tracks; undecided/unclear ones stay pending."""
    ledger = load_ledger()
    decisions = review.load_corrections(PENDING_DECISIONS_PATH)
    changes, resolved = [], {}
    for key, entry in ledger.items():
        decision = decisions.get(entry["id"])
        if (
            entry["status"] != "pending"
            or not decision
            or decision["verdict"] == "unclear"
        ):
            continue
        row = plan.build_apply_row(entry["record"], {}, entry["a"], entry["b"])
        final = plan.resolve_final({**row, "auto": False}, decision)
        current = apply_mod.read_current(records.MUSIC_ROOT / entry["id"])
        change = (
            plan.build_change(entry["id"], current, final, DEFAULT_SEPARATORS)
            if final
            else None
        )
        changes += [change] if change else []
        resolved[key] = _entry("applied" if change else "kept", entry["id"])
    logger.info(f"{len(changes)} pending tracks would change, {len(resolved)} resolved")
    if not write:
        return {"changes": len(changes), "resolved": len(resolved), "written": 0}
    _, written, failed = apply_mod.apply_changes(changes) if changes else (None, 0, [])
    keep = {k: v for k, v in resolved.items() if v["id"] not in failed}
    save_ledger({**ledger, **keep})
    if written and sync_url:
        trigger_sync(sync_url)
    return {"changes": len(changes), "resolved": len(keep), "written": written}
