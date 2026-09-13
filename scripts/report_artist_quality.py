"""Before/after report for uploader vs reposter quality separation (ticket #60).

Reads the database (use a copy) and writes Markdown. Never writes to the DB.

Usage:
    uv run python scripts/report_artist_quality.py \\
        --db /path/to/copy.db --out docs/reports/artist-quality-before-after.md
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from loguru import logger

# Scripts run from the repo root; ``web`` is a source tree, not an installed package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from music_minion.core.database import get_database_path  # noqa: E402
from web.backend.artist_quality import (  # noqa: E402
    artist_quality_report,
    render_artist_quality_markdown,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=get_database_path())
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        report = artist_quality_report(conn)
    finally:
        conn.close()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_artist_quality_markdown(report))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    logger.info(f"compared {report['decided_tracks']} decided tracks → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
