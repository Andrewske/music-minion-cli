#!/bin/bash
# Run a one-off tool against the live DB, inside the pi's container.
#
# Usage:
#   scripts/on-pi.sh music-minion locate-opus /home/kevin/Music/EDM/x --apply
#   scripts/on-pi.sh scripts/check_playlists.py [args...]   # streams the local script
set -euo pipefail

CONTAINER="music-minion-web"
[ $# -ge 1 ] || { echo "usage: $0 <music-minion args | script.py args>" >&2; exit 1; }

if [[ "$1" == *.py ]]; then
    script="$1"; shift
    ssh piserver docker exec -i "$CONTAINER" /app/.venv/bin/python - "$@" < "$script"
elif [ "$1" = "music-minion" ]; then
    shift
    ssh -t piserver docker exec -it "$CONTAINER" /app/.venv/bin/music-minion "$@"
else
    echo "error: expected 'music-minion ...' or a .py script, got '$1'" >&2
    exit 1
fi
