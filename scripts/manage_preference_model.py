"""Train, promote, inspect, rescore, or roll back preference models.

Examples:
    uv run python scripts/manage_preference_model.py train --version keep-2026-09-12
    uv run python scripts/manage_preference_model.py promote keep-2026-09-12
    uv run python scripts/manage_preference_model.py rollback
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from music_minion.core.database import get_db_connection
from music_minion.core.output import log
from web.backend.preference_model import evaluate_model
from web.backend.preference_scoring import (
    promote_model,
    rescore_unresolved_feed,
    rollback_model,
    scoring_health,
    store_model,
    training_examples_from_decisions,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    train = commands.add_parser("train")
    train.add_argument("--version", required=True)
    train.add_argument("--bootstrap-iterations", type=int, default=1_000)
    promote = commands.add_parser("promote")
    promote.add_argument("version")
    commands.add_parser("rollback")
    rescore = commands.add_parser("rescore")
    rescore.add_argument("--version")
    status = commands.add_parser("status")
    status.add_argument("--version")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.command == "rescore":
        count = rescore_unresolved_feed(args.version)
        log(f"✅ Rescored {count} feed candidates", level="info")
        return 0

    with get_db_connection() as conn:
        if args.command == "train":
            examples = training_examples_from_decisions(conn)
            artifact, report = evaluate_model(
                examples,
                args.version,
                bootstrap_iterations=args.bootstrap_iterations,
            )
            store_model(
                conn,
                artifact,
                status="candidate",
                ship_gate_passed=report["ship_gate_passed"],
            )
            conn.execute(
                """
                UPDATE preference_rollout_state
                SET decisions_at_last_training = ?, last_training_at = ?
                WHERE id = 1
                """,
                (len(examples), datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            log(
                f"✅ Stored candidate {args.version}: {report['recommendation']}",
                level="info",
            )
            return 0
        if args.command == "promote":
            promote_model(conn, args.version)
            conn.execute(
                "UPDATE preference_rollout_state SET active_model_version = ?, "
                "last_promotion_at = CURRENT_TIMESTAMP WHERE id = 1",
                (args.version,),
            )
            conn.commit()
            log(
                f"✅ Promoted {args.version}; run rescore to refresh candidates",
                level="info",
            )
            return 0
        if args.command == "rollback":
            version = rollback_model(conn)
            conn.execute(
                "UPDATE preference_rollout_state SET active_model_version = ?, "
                "builder_mode = 'chronological' WHERE id = 1",
                (version,),
            )
            conn.commit()
            log(
                f"✅ Rolled back to {version or 'chronological/no model'}",
                level="info",
            )
            return 0

        version = args.version
        if not version:
            active = conn.execute(
                "SELECT version FROM preference_models WHERE status = 'active' LIMIT 1"
            ).fetchone()
            version = active["version"] if active else None
        if not version:
            log("No active preference model", level="info")
            return 0
        health = scoring_health(conn, version)
        log(json.dumps({"version": version, **health}, sort_keys=True), level="info")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
