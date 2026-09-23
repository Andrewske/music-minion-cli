"""Leakage-safe offline evaluation of the keep-probability model (ticket #61).

Reads a SQLite database (by default the live one, ideally a copy), rebuilds
one leakage-safe example per decided track, and writes a Markdown report plus
an optional JSON dump. Never writes to the database and never changes
production selection.

Usage:
    uv run python scripts/evaluate_keep_model.py \\
        --db /path/to/copy.db --out docs/reports/keep-model-evaluation.md
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

# Scripts run from the repo root; ``web`` is a source tree, not an installed package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from music_minion.core.database import get_database_path  # noqa: E402
from web.backend.keep_decisions import timeline_track_decisions  # noqa: E402
from web.backend.keep_model_dataset import training_examples  # noqa: E402
from web.backend.keep_model_report import render_evaluation_markdown  # noqa: E402
from web.backend.jev_scorer import load_taste_profile  # noqa: E402
from web.backend.preference_model import (  # noqa: E402
    TrainingExample,
    artifact_to_json,
    chronological_split,
    evaluate_model,
)

LIMITATIONS: tuple[str, ...] = (
    "Decision times are proxies: a track decided in playlist batch k is stamped "
    "with the start of the sync that created batch k+1, so ordering is exact "
    "across sync cycles but unknown within one. Splits keep each cycle whole.",
    "`ranking`, `tier`, and `is_following` have no history table; current values "
    "stand in for their values at decision time. Rank edits and follows made "
    "after liking an artist's track leak mildly into rank and follow features. "
    "The `rank_signals` and `uploader` ablations bound that effect.",
    "Uploader identity is resolved by SoundCloud user ID when the metadata "
    "backfill has run, else by an upload event, else by normalized artist name. "
    "Name matching only resolves followed artists, so `followed_uploader` is "
    "partly 'uploader is a known artist'.",
    "`seen_at` for reposts was backfilled on 2026-04-15; reposts on tracks "
    "decided before that are bounded by repost time only, so a reposter who "
    "arrived after an early decision can still count.",
    "Genre is static track metadata but is NULL for most legacy rows until the "
    "metadata backfill runs, so the genre feature is effectively unused here.",
    "Decided tracks are those the builder chose to surface; tracks the user "
    "would have kept but never saw are absent, so the model learns 'keep given "
    "surfaced', not 'keep' in general.",
    "About 880 examples with ~140 in the test window: intervals are wide, and "
    "a taste or supply shift between windows shows up as drift, not error. "
    "Compare the validation AUC in the regularization grid with the test AUC "
    "to see how much the two windows disagree.",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=get_database_path())
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--version", default="offline-keep-v2")
    parser.add_argument("--bootstrap-iterations", type=int, default=1_000)
    parser.add_argument(
        "--jev-cache",
        type=Path,
        default=Path("data/jev_eval_cache.json"),
        help="Prediction cache from build_jev_eval_cache.py; merged as the "
        "'jev' system when it covers the whole test split",
    )
    return parser.parse_args()


def _jev_system(
    cache_path: Path, examples: list[TrainingExample]
) -> dict[str, list[float]]:
    """{'jev': test-split probabilities} when the cache fully covers it."""
    profile = load_taste_profile()
    if profile is None or not cache_path.exists():
        return {}
    _, profile_version = profile
    cache = json.loads(cache_path.read_text())
    test = chronological_split(examples).test
    probabilities: list[float] = []
    for example in test:
        entry = cache.get(
            f"{example.soundcloud_id}|{example.decided_at}|{profile_version}"
        )
        if entry is None:
            logger.warning(
                f"jev cache misses {example.soundcloud_id} for profile "
                f"{profile_version}; skipping the jev comparison"
            )
            return {}
        probabilities.append(float(entry["probability"]))
    return {"jev": probabilities}


def _open_readonly(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def main() -> int:
    args = _parse_args()
    now = datetime.now(timezone.utc)
    conn = _open_readonly(args.db)
    try:
        decisions = timeline_track_decisions(conn, now=now)
    finally:
        conn.close()
    examples = training_examples(decisions)
    if len(examples) < 50:
        logger.error(f"need at least 50 decided tracks, found {len(examples)}")
        return 2
    artifact, report = evaluate_model(
        examples,
        args.version,
        bootstrap_iterations=args.bootstrap_iterations,
        extra_systems=_jev_system(args.jev_cache, examples),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_evaluation_markdown(report, LIMITATIONS, args.db.name))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.artifact:
        args.artifact.parent.mkdir(parents=True, exist_ok=True)
        args.artifact.write_text(artifact_to_json(artifact) + "\n")
    logger.info(
        f"evaluated {len(examples)} decisions: {report['recommendation']} → {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
