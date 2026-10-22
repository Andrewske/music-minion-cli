#!/bin/bash
# Copy a consistent snapshot of the pi's live DB to this machine for dev work.
# Uses SQLite's backup API (safe while the container is writing), never rsync.
#
# Usage: scripts/pull-db-snapshot.sh [dest]
#   then: MUSIC_MINION_DB_PATH=<dest> uv run music-minion --web
set -euo pipefail

DEST="${1:-$HOME/.local/share/music-minion/dev/music_minion.db}"
REMOTE_TMP="/tmp/music-minion-snapshot-$$.db"
LIVE_DB="/home/kevin/.local/share/music-minion/music_minion.db"

mkdir -p "$(dirname "$DEST")"
ssh piserver "python3 -c '
import sqlite3, sys
src = sqlite3.connect(\"file:\" + sys.argv[1] + \"?mode=ro\", uri=True)
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
assert dst.execute(\"pragma integrity_check\").fetchone()[0] == \"ok\"
' $LIVE_DB $REMOTE_TMP"
scp -q "piserver:$REMOTE_TMP" "$DEST"
ssh piserver "rm -f $REMOTE_TMP"
rm -f "$DEST-wal" "$DEST-shm"

echo "Snapshot: $DEST"
echo "Run: MUSIC_MINION_DB_PATH=$DEST uv run music-minion --web"
