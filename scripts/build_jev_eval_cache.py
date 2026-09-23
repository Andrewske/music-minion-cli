"""Replay ledger decisions through Jev and cache the probabilities.

Builds leakage-safe (as-of-decision) states from the same TrainingExamples
the offline evaluation uses, asks Jev the production Noul question, and
writes a resumable JSON cache that ``evaluate_keep_model.py`` merges into
its system comparison as the ``jev`` row.

Known asymmetry vs live scoring: eval states carry decision-time features
but no artist/reposter names (there is no name history), and the taste
profile is always the current one. Re-run after taste-profile edits.

Usage:
    uv run python scripts/build_jev_eval_cache.py \\
        --db /path/to/copy.db --cache data/jev_eval_cache.json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from music_minion.core.database import get_database_path  # noqa: E402
from web.backend import jev_client, jev_scorer  # noqa: E402
from web.backend.keep_decisions import timeline_track_decisions  # noqa: E402
from web.backend.keep_model_dataset import training_examples  # noqa: E402
from web.backend.preference_model import TrackFeatures, TrainingExample  # noqa: E402

DEFAULT_CACHE = Path("data/jev_eval_cache.json")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=get_database_path())
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="max new predictions this run (resume later)",
    )
    return parser.parse_args()


def cache_key(example: TrainingExample, profile_version: str) -> str:
    return f"{example.soundcloud_id}|{example.decided_at}|{profile_version}"


def eval_track_dict(features: TrackFeatures) -> dict[str, Any]:
    """Mirror of the live state shape, built from as-of-decision features."""
    return {
        "track": {
            "title": features.title,
            "genre": features.genre,
            "duration_min": round((features.duration_ms or 0) / 60_000, 2) or None,
            "event_type": features.event_type,
            "release_age_days": features.release_age_days,
            "uploader": {
                "name": None,
                "followed": features.followed_uploader,
                "rank": features.uploader_rank,
                "keep_rate": features.uploader_keep_rate,
                "rated_count": features.uploader_rated_count,
            },
            "reposters": [
                {
                    "name": None,
                    "rank": features.best_reposter_rank,
                    "keep_rate": features.reposter_keep_rate,
                    "rated_count": features.reposter_rated_count,
                }
            ]
            if features.reposter_count
            else [],
            "reposter_count": features.reposter_count,
            "top200_reposter_count": features.top200_reposter_count,
        },
        "history": {"overall_keep_rate": None, "decisions_total": None},
    }


def load_cache(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def main() -> int:
    args = _parse_args()
    config = jev_client.get_jev_config()
    if config is None:
        logger.error("JEV_API_KEY not configured")
        return 2
    profile = jev_scorer.load_taste_profile()
    if profile is None:
        logger.error("taste profile missing")
        return 2
    profile_text, profile_version = profile

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        decisions = timeline_track_decisions(conn, now=datetime.now(timezone.utc))
    finally:
        conn.close()
    examples = training_examples(decisions)

    cache = load_cache(args.cache)
    pending = [e for e in examples if cache_key(e, profile_version) not in cache]
    logger.info(f"{len(examples)} examples, {len(pending)} uncached")
    added = 0
    for example in pending[: args.limit]:
        state = jev_scorer.build_state(eval_track_dict(example.features), profile_text)
        try:
            prediction = jev_client.ask_noul(config, state, jev_scorer.NOUL_QUESTION)
        except Exception:
            logger.exception(f"jev failed for {example.soundcloud_id}; stopping")
            break
        cache[cache_key(example, profile_version)] = {
            "probability": prediction.probability,
            "confidence": prediction.confidence,
            "model_id": prediction.model_id,
        }
        added += 1
        if added % 25 == 0:
            args.cache.parent.mkdir(parents=True, exist_ok=True)
            args.cache.write_text(json.dumps(cache, indent=1, sort_keys=True))
            logger.info(f"cached {added}/{len(pending)}")
        time.sleep(0.1)
    args.cache.parent.mkdir(parents=True, exist_ok=True)
    args.cache.write_text(json.dumps(cache, indent=1, sort_keys=True))
    logger.info(f"done: +{added}, cache now {len(cache)} entries → {args.cache}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
