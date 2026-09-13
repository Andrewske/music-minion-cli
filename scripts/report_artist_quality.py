"""Write the issue #60 uploader/reposter quality before-and-after report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from music_minion.core.database import get_db_connection
from music_minion.core.output import log
from web.backend.preference_scoring import artist_quality_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with get_db_connection() as conn:
        report = artist_quality_report(conn)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    log(
        f"✅ Compared {report['unique_decided_tracks']} decided tracks → {args.output}",
        level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
