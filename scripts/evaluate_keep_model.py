"""Evaluate the SoundCloud keep-probability model without changing rollout state.

Usage:
    uv run python scripts/evaluate_keep_model.py --output reports/keep-model.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from music_minion.core.database import get_db_connection
from music_minion.core.output import log
from web.backend.preference_model import artifact_to_json, evaluate_model
from web.backend.preference_scoring import training_examples_from_decisions


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--version", default="offline-v1")
    parser.add_argument("--bootstrap-iterations", type=int, default=1_000)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    with get_db_connection() as conn:
        examples = training_examples_from_decisions(conn)
    if len(examples) < 5:
        log(
            f"❌ Need at least 5 leakage-safe keep/nope decisions; found {len(examples)}",
            level="error",
        )
        return 2
    artifact, report = evaluate_model(
        examples,
        version=args.version,
        bootstrap_iterations=args.bootstrap_iterations,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.artifact:
        args.artifact.parent.mkdir(parents=True, exist_ok=True)
        args.artifact.write_text(artifact_to_json(artifact) + "\n")
    log(
        f"✅ Evaluated {len(examples)} decisions: {report['recommendation']} → {args.output}",
        level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
