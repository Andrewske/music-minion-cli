"""Unattended cleanup of newly downloaded tracks (runs after the nightly scdl job).

New = an MP3 or M4A in the year folder whose SoundCloud URL (or path) is not in the
ledger. Each new track is cleaned twice; when both runs agree and neither
hedges, the tags are written. Everything else waits in the ledger as
"pending" for the web Tag review page (or `review --mode pending` +
`apply --pending --write`).

Ledger concurrency: the host-side nightly ingest and the web container both
read-modify-write ledger.json over a bind mount. Every read-modify-write runs
under `ledger_lock()` (an exclusive flock on a sidecar file, which works across
the mount), re-reads the ledger inside the lock and merges only its own keys.
The lock is never held while codex runs. Plain reads (review rows, counts) skip
the lock: saves are an atomic os.replace, so a reader always sees a whole file.
"""

import fcntl
import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from loguru import logger
from mutagen import MutagenError

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

LOCK_TIMEOUT_S = 30.0

Ledger = dict[str, dict[str, Any]]
Entry = dict[str, Any]


class LedgerBusyError(TimeoutError):
    """Another process held the ledger lock past the timeout."""


class PendingNotFoundError(LookupError):
    """No pending ledger entry for a track id (unknown or already resolved)."""


class TagWriteError(RuntimeError):
    """Writing the reviewed tags to the audio file failed."""


def ledger_key(track_id: str, tags: dict[str, str]) -> str:
    """SoundCloud URL survives renames/moves; fall back to the path."""
    return tags.get("source_url") or track_id


def load_ledger() -> Ledger:
    return json.loads(LEDGER_PATH.read_text()) if LEDGER_PATH.exists() else {}


def save_ledger(ledger: Ledger) -> None:
    """Atomic replace; callers that modify the ledger hold ledger_lock()."""
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = LEDGER_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(ledger, indent=1, ensure_ascii=False))
    os.replace(temp, LEDGER_PATH)


def lock_path() -> Path:
    """Sidecar lock file. Never deleted: a new inode would split the lock."""
    return LEDGER_PATH.with_name(LEDGER_PATH.name + ".lock")


def _acquire(fd: int, timeout: float, path: Path) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise LedgerBusyError(
                    f"Ledger lock {path} still held after {timeout:.0f}s"
                ) from None
            time.sleep(0.05)


@contextmanager
def ledger_lock(timeout: float | None = None) -> Iterator[None]:
    """Exclusive flock around one ledger read-modify-write (not re-entrant)."""
    path = lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDONLY | os.O_CREAT, 0o666)
    try:
        _acquire(fd, LOCK_TIMEOUT_S if timeout is None else timeout, path)
        yield
    finally:
        os.close(fd)  # closing the descriptor releases the flock


def _save_merged(entries: Ledger) -> None:
    """Caller holds the lock. Re-reads right before saving so only these keys
    change, even if a writer that ignores the lock touched the file meanwhile."""
    save_ledger({**load_ledger(), **entries})


def merge_ledger(entries: Ledger) -> None:
    """Re-read under the lock and write back only these keys."""
    with ledger_lock():
        _save_merged(entries)


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
    with ledger_lock():
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
    """Codex runs unlocked; only the final merge of new keys takes the lock."""
    new = find_new(scan(records.MUSIC_ROOT / year), load_ledger())
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
    merge_ledger(entries)
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


def _pending_row(entry: Entry) -> dict | None:
    """One review row, or None when the file is gone or unreadable."""
    path = records.MUSIC_ROOT / entry["id"]
    try:
        tags = records.read_tags(path)
    except (OSError, MutagenError, ValueError):
        logger.warning(f"Pending track {entry['id']} unreadable at {path}; skipped")
        return None
    row = plan.build_apply_row(entry["record"], tags, entry["a"], entry["b"])
    raw = review.raw_view(entry["record"], tags.get("source_url"))
    unclear = bool(entry.get("unclear_at"))
    return {
        **row,
        "auto": False,
        "left": row["current"],
        "raw": raw,
        "unclear": unclear,
    }


def pending_rows(ledger: Ledger) -> list[dict]:
    """Review rows for every pending track, current tags read fresh.

    Tracks marked unclear sort last so the queue starts with fresh work.
    """
    rows = [
        row
        for entry in ledger.values()
        if entry["status"] == "pending" and (row := _pending_row(entry))
    ]
    return sorted(rows, key=lambda row: row["unclear"])


def pending_count(ledger: Ledger) -> int:
    return sum(1 for entry in ledger.values() if entry["status"] == "pending")


def _is_decided(entry: Entry, decision: dict | None) -> bool:
    return (
        entry["status"] == "pending"
        and bool(decision)
        and decision["verdict"] != "unclear"
    )


def resolve_entry(
    entry: Entry, decision: dict, current: dict[str, str]
) -> tuple[dict | None, Entry]:
    """Pure per-entry step: (tag change to write or None, resolved ledger entry).

    Shared by the CLI (`apply --pending`) and the web decision endpoint.
    """
    row = plan.build_apply_row(entry["record"], {}, entry["a"], entry["b"])
    final = plan.resolve_final({**row, "auto": False}, decision)
    change = (
        plan.build_change(entry["id"], current, final, DEFAULT_SEPARATORS)
        if final
        else None
    )
    status = "applied" if change else "kept"
    return change, _entry(status, entry["id"], verdict=decision["verdict"])


def _resolve_one(entry: Entry, decision: dict) -> tuple[dict | None, Entry]:
    current = apply_mod.read_current(records.MUSIC_ROOT / entry["id"])
    return resolve_entry(entry, decision, current)


def plan_resolutions(ledger: Ledger, decisions: dict) -> tuple[list[dict], Ledger]:
    """Changes to write and resolved entries for every decided pending track."""
    changes, resolved = [], {}
    for key, entry in ledger.items():
        decision = decisions.get(entry["id"])
        if not _is_decided(entry, decision):
            continue
        change, resolved[key] = _resolve_one(entry, decision)
        changes += [change] if change else []
    return changes, resolved


def write_resolved(changes: list[dict], resolved: Ledger) -> tuple[int, Ledger]:
    """Apply step: write tags (backup + undo log); drop entries whose write failed."""
    _, written, failed = apply_mod.apply_changes(changes) if changes else (None, 0, [])
    return written, {k: v for k, v in resolved.items() if v["id"] not in failed}


def resolve_pending(write: bool, sync_url: str | None) -> dict:
    """Apply reviewed pending tracks; undecided/unclear ones stay pending."""
    decisions = review.load_corrections(PENDING_DECISIONS_PATH)
    with ledger_lock():
        ledger = load_ledger()
        changes, resolved = plan_resolutions(ledger, decisions)
        logger.info(
            f"{len(changes)} pending tracks would change, {len(resolved)} resolved"
        )
        if not write:
            return {"changes": len(changes), "resolved": len(resolved), "written": 0}
        written, keep = write_resolved(changes, resolved)
        _save_merged(keep)
    if written and sync_url:
        trigger_sync(sync_url)
    return {"changes": len(changes), "resolved": len(keep), "written": written}


def _pending_key(ledger: Ledger, track_id: str) -> str:
    key = next(
        (
            k
            for k, e in ledger.items()
            if e["id"] == track_id and e["status"] == "pending"
        ),
        None,
    )
    if key is None:
        raise PendingNotFoundError(
            f"No pending ledger entry for {track_id!r} (unknown or already resolved)"
        )
    return key


def _apply_decision(ledger: Ledger, key: str, decision: dict) -> tuple[Entry, int]:
    """Under the lock: resolve one entry, write its tags, return (entry, written)."""
    entry = ledger[key]
    if decision["verdict"] == "unclear":
        return {**entry, "unclear_at": datetime.now().isoformat()}, 0
    change, resolved = _resolve_one(entry, decision)
    written, keep = write_resolved([change] if change else [], {key: resolved})
    if key not in keep:
        raise TagWriteError(
            f"Tag write failed for {entry['id']!r}; ledger entry left pending"
        )
    return resolved, written


def decide_pending(track_id: str, decision: dict) -> dict:
    """Apply one review decision right away (the web Tag review page).

    The lock covers re-read, tag write and save, so a concurrent ingest merge
    or a second decision for the same track can't interleave. One file write
    takes well under a second; codex never runs here.
    """
    with ledger_lock():
        ledger = load_ledger()
        key = _pending_key(ledger, track_id)
        entry, written = _apply_decision(ledger, key, decision)
        _save_merged({key: entry})
    logger.info(f"Tag review: {track_id} -> {decision['verdict']} ({entry['status']})")
    return {"id": track_id, "status": entry["status"], "written": written > 0}
