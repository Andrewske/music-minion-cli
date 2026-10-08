"""CLI: extract | gold | clean | eval | review | apply | restore.

uv run python -m music_minion.domain.metadata_cleanup extract --year 2026
uv run python -m music_minion.domain.metadata_cleanup gold
uv run python -m music_minion.domain.metadata_cleanup clean --input gold --limit 30
uv run python -m music_minion.domain.metadata_cleanup eval <run_dir>
uv run python -m music_minion.domain.metadata_cleanup review [--mode apply]
uv run python -m music_minion.domain.metadata_cleanup apply [--write]
uv run python -m music_minion.domain.metadata_cleanup restore <backup_dir>
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from loguru import logger

from music_minion.domain.metadata_cleanup import apply as apply_mod
from music_minion.domain.metadata_cleanup import (
    batching,
    evaluate,
    gold,
    plan,
    records,
    review,
)
from music_minion.domain.metadata_cleanup.render import DEFAULT_SEPARATORS
from music_minion.domain.metadata_cleanup.normalize import normalize_proposal
from music_minion.domain.metadata_cleanup.codex_runner import CodexSettings, run_batches
from music_minion.domain.metadata_cleanup.soundcloud_fetch import fetch_all

RECORDS_DIR = records.WORK_DIR / "records"
RUNS_DIR = records.WORK_DIR / "runs"
SC_CACHE = records.WORK_DIR / "soundcloud-cache.json"


def _scan(folder: Path) -> list[tuple[Path, dict[str, str]]]:
    return [(path, records.read_tags(path)) for path in records.list_mp3s(folder)]


def _resolve(scanned: list[tuple[Path, dict[str, str]]]) -> dict[str, dict | None]:
    urls = sorted({tags["source_url"] for _, tags in scanned if "source_url" in tags})
    logger.info(f"Resolving {len(urls)} SoundCloud permalinks (cached where possible)")
    return fetch_all(urls, SC_CACHE)


def cmd_extract(args: argparse.Namespace) -> None:
    scanned = _scan(records.MUSIC_ROOT / args.year)
    sc = _resolve(scanned)
    rows = [
        records.build_record(path, tags, sc.get(tags.get("source_url", "")), raw=True)
        for path, tags in scanned
    ]
    count = records.write_jsonl(RECORDS_DIR / f"{args.year}.jsonl", rows)
    with_sc = sum(1 for row in rows if row["soundcloud"])
    logger.info(f"Wrote {count} records ({with_sc} with SoundCloud data)")


def _gold_row(path: Path, tags: dict[str, str], sc: dict | None) -> dict | None:
    expected = gold.expected_from_tags(tags)
    if not sc or not expected:
        return None
    row = records.build_record(path, tags, sc, raw=False)
    return {**row, "expected": expected}


def cmd_gold(args: argparse.Namespace) -> None:
    scanned = [
        item
        for year in gold.FIXED_MONTHS
        for item in _scan(records.MUSIC_ROOT / year)
        if gold.is_fixed_month(records.track_id(item[0])) and "source_url" in item[1]
    ]
    sc = _resolve(scanned)
    rows = [_gold_row(path, tags, sc.get(tags["source_url"])) for path, tags in scanned]
    kept = [row for row in rows if row]
    records.write_jsonl(RECORDS_DIR / "gold.jsonl", kept)
    logger.info(
        f"Gold set: {len(kept)} of {len(scanned)} fixed tracks with SoundCloud data"
    )


def _sort_key(record: dict) -> str:
    sc = record.get("soundcloud") or {}
    return (sc.get("uploader") or record["filename"]).casefold()


def _new_run_dir(args: argparse.Namespace, batch_count: int) -> Path:
    run_dir = RUNS_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{args.input}-{args.label}"
    run_dir.mkdir(parents=True)
    settings = CodexSettings(args.model, args.reasoning, not args.no_web_search)
    config = {**vars(args), "settings": settings.__dict__, "batches": batch_count}
    (run_dir / "config.json").write_text(json.dumps(config, indent=1, default=str))
    return run_dir


def _existing_proposals(run_dir: Path | None) -> list[dict]:
    if run_dir is None or not (run_dir / "proposals.jsonl").exists():
        return []
    return records.read_jsonl(run_dir / "proposals.jsonl")


def cmd_clean(args: argparse.Namespace) -> None:
    """Run codex over a records file. --resume <run_dir> fills only missing tracks."""
    resume = Path(args.resume) if args.resume else None
    existing = _existing_proposals(resume)
    done = {proposal["id"] for proposal in existing}
    rows = sorted(
        records.read_jsonl(RECORDS_DIR / f"{args.input}.jsonl"), key=_sort_key
    )
    rows = [row for row in rows if row["id"] not in done]
    rows = rows[: args.limit] if args.limit else rows
    batches = batching.make_batches(rows, args.batch_size)
    run_dir = resume or _new_run_dir(args, len(batches))
    logger.info(f"{len(rows)} tracks in {len(batches)} batches -> {run_dir}")
    settings = CodexSettings(args.model, args.reasoning, not args.no_web_search)
    results = run_batches(batches, settings, args.workers)
    batch_log = "batches-resume.jsonl" if resume else "batches.jsonl"
    records.write_jsonl(run_dir / batch_log, results)
    uploaders = {r["id"]: (r.get("soundcloud") or {}).get("uploader") for r in rows}
    proposals = existing + [
        normalize_proposal(track, uploaders.get(track["id"]))
        for result in results
        for track in result["tracks"]
        if track["id"] in uploaders  # drop ids the model mangled
    ]
    records.write_jsonl(run_dir / "proposals.jsonl", proposals)
    logger.info(
        f"{len(proposals)} proposals in run ({len(proposals) - len(existing)} new)"
    )


def _load_gold() -> list[dict]:
    """Gold rows with reviewed corrections applied (unclear/excluded dropped)."""
    rows = records.read_jsonl(RECORDS_DIR / "gold.jsonl")
    return gold.apply_corrections(rows, review.load_corrections())


def _load_proposals(run_dir: Path) -> dict[str, dict]:
    return {p["id"]: p for p in records.read_jsonl(run_dir / "proposals.jsonl")}


def cmd_eval(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    metrics, rows = evaluate.score(_load_gold(), _load_proposals(run_dir))
    metrics["reviewed"] = len(review.load_corrections())
    (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=1))
    (run_dir / "report.txt").write_text(evaluate.render_report(metrics, rows))
    logger.info(f"{json.dumps(metrics)}\nReport: {run_dir / 'report.txt'}")


def _latest_full_runs(input_name: str, count: int) -> list[Path]:
    """Most recent complete (no --limit) runs for an input, oldest first."""
    runs = [
        run
        for run in sorted(RUNS_DIR.glob(f"*-{input_name}-*"))
        if (run / "proposals.jsonl").exists()
        and json.loads((run / "config.json").read_text()).get("limit") == 0
    ]
    if len(runs) < count:
        raise SystemExit(
            f"Need {count} full `clean --input {input_name}` runs in {RUNS_DIR}, "
            f"found {len(runs)}"
        )
    return runs[-count:]


def _apply_runs(args: argparse.Namespace) -> list[Path]:
    if args.runs:
        return [Path(run) for run in args.runs]
    return _latest_full_runs(args.year, 2)


def _apply_rows(year: str, run_a: Path, run_b: Path) -> list[dict]:
    """Rows for every track both runs answered, with current tags read fresh."""
    a, b = _load_proposals(run_a), _load_proposals(run_b)
    rows = []
    for record in records.read_jsonl(RECORDS_DIR / f"{year}.jsonl"):
        if record["id"] not in a or record["id"] not in b:
            continue
        tags = records.read_tags(records.MUSIC_ROOT / record["id"])
        row = plan.build_apply_row(record, tags, a[record["id"]], b[record["id"]])
        rows.append({**row, "raw": review.raw_view(record, tags.get("source_url"))})
    return rows


def cmd_review(args: argparse.Namespace) -> None:
    """Gold mode shows raw gold (not corrected) so every original mismatch shows."""
    if args.mode == "apply":
        run_a, run_b = _apply_runs(args)
        rows = [
            {**row, "left": row["current"]}
            for row in _apply_rows(args.year, run_a, run_b)
        ]
        session = review.ReviewSession(
            mode="apply",
            title=f"{args.year}: A={run_a.name} B={run_b.name}",
            rows=rows,
            decisions_path=review.apply_decisions_path(args.year),
            labels={"left": "Current tags", "a": "Run A", "b": "Run B"},
        )
    else:
        run_dir = Path(args.runs[0]) if args.runs else _latest_full_runs("gold", 1)[0]
        gold_rows = records.read_jsonl(RECORDS_DIR / "gold.jsonl")
        session = review.ReviewSession(
            mode="gold",
            title=run_dir.name,
            rows=review.build_gold_rows(gold_rows, _load_proposals(run_dir)),
            decisions_path=review.CORRECTIONS_PATH,
            labels={"left": "Gold (current tags)", "a": "Model"},
        )
    review.serve(session, args.port)


def _planned_changes(args: argparse.Namespace) -> tuple[list[dict], dict[str, int]]:
    run_a, run_b = _apply_runs(args)
    decisions = review.load_corrections(review.apply_decisions_path(args.year))
    changes, counts = (
        [],
        {"auto": 0, "reviewed": 0, "undecided": 0, "kept": 0, "unchanged": 0},
    )
    for row in _apply_rows(args.year, run_a, run_b):
        decision = decisions.get(row["id"])
        final = plan.resolve_final(row, decision)
        if final is None:
            counts["kept" if decision else "undecided"] += 1
            continue
        current = apply_mod.read_current(records.MUSIC_ROOT / row["id"])
        diff = plan.tag_changes(current, plan.to_tags(final, DEFAULT_SEPARATORS))
        if not diff:
            counts["unchanged"] += 1
            continue
        counts["reviewed" if decision else "auto"] += 1
        new = {**current, **{key: new for key, (_, new) in diff.items()}}
        changes.append({"id": row["id"], "diff": diff, "new": new})
    return changes, counts


def _render_diff(changes: list[dict]) -> str:
    lines = []
    for change in changes:
        lines.append(change["id"])
        for key, (old, new) in change["diff"].items():
            lines.append(f"  {key:8} {old!r}\n  {'':8} -> {new!r}")
    return "\n".join(lines) + "\n"


def cmd_apply(args: argparse.Namespace) -> None:
    """Dry run by default: writes the diff to a file. --write changes the MP3s."""
    changes, counts = _planned_changes(args)
    diff_path = records.WORK_DIR / f"apply-{args.year}-diff.txt"
    diff_path.write_text(_render_diff(changes))
    logger.info(f"{len(changes)} files would change {counts}. Diff: {diff_path}")
    if not args.write:
        logger.info("Dry run only. Re-run with --write to apply.")
        return
    backup, written, failed = apply_mod.apply_changes(changes)
    logger.info(
        f"Wrote {written} files, {len(failed)} failed. Backup/undo log: {backup}"
    )
    logger.info(
        "Syncthing will carry the files to the pi; then refresh its DB with "
        "`curl -k -X POST https://music.piserver:8443/api/sync`"
    )


def cmd_restore(args: argparse.Namespace) -> None:
    restored = apply_mod.restore(Path(args.backup_dir))
    logger.info(f"Restored {restored} files from {args.backup_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="metadata_cleanup")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("extract").add_argument("--year", default="2026")
    sub.add_parser("gold")
    clean = sub.add_parser("clean")
    clean.add_argument("--input", default="gold", help="records file stem: gold | 2026")
    clean.add_argument("--limit", type=int, default=0)
    clean.add_argument("--batch-size", type=int, default=10)
    clean.add_argument("--model", default="gpt-6-luna")
    clean.add_argument("--reasoning", default="medium")
    clean.add_argument("--no-web-search", action="store_true")
    clean.add_argument("--workers", type=int, default=3)
    clean.add_argument("--label", default="run")
    clean.add_argument("--resume", help="existing run dir; only run its missing tracks")
    sub.add_parser("eval").add_argument("run_dir")
    review_cmd = sub.add_parser("review")
    review_cmd.add_argument("--mode", choices=("gold", "apply"), default="gold")
    review_cmd.add_argument("--year", default="2026")
    review_cmd.add_argument("--runs", nargs="+", help="gold: 1 run dir; apply: 2")
    review_cmd.add_argument("--port", type=int, default=8765)
    apply_cmd = sub.add_parser("apply")
    apply_cmd.add_argument("--year", default="2026")
    apply_cmd.add_argument("--runs", nargs=2, help="run A and run B dirs")
    apply_cmd.add_argument("--write", action="store_true")
    sub.add_parser("restore").add_argument("backup_dir")
    return parser


COMMANDS = {
    "extract": cmd_extract,
    "gold": cmd_gold,
    "clean": cmd_clean,
    "eval": cmd_eval,
    "review": cmd_review,
    "apply": cmd_apply,
    "restore": cmd_restore,
}

if __name__ == "__main__":
    parsed = build_parser().parse_args()
    COMMANDS[parsed.command](parsed)
