#!/bin/bash
# Runs ON the pi: build music-minion:<sha> from an exported source tree,
# snapshot the DB, swap :current, and roll back if /health doesn't come up.
#
# Usage: deploy-on-pi.sh <source-dir> <sha>
# Callers: scripts/deploy-to-pi.sh (manual, from a laptop) and
# scripts/pi-autodeploy.sh (systemd timer). Records the live sha in
# $DEPLOY_DIR/.deployed-sha so the timer knows what's already shipped.
set -euo pipefail

SRC_DIR=${1:?usage: deploy-on-pi.sh <source-dir> <sha>}
SHA=${2:?usage: deploy-on-pi.sh <source-dir> <sha>}   # full sha
TAG=${SHA:0:7}
DEPLOY_DIR=/home/kevin/music-minion-deploy
LIVE_DB=/home/kevin/.local/share/music-minion/music_minion.db
BACKUP_DIR=/home/kevin/backups/music-minion
HEALTH_TIMEOUT_S=120

build_image() {
    echo "==> Building music-minion:$TAG"
    docker build -q -t "music-minion:$TAG" "$SRC_DIR"
}

snapshot_db() {
    local dest
    dest="$BACKUP_DIR/pi-predeploy-$TAG-$(date +%Y%m%d-%H%M%S).db"
    echo "==> Snapshotting DB to $dest"
    mkdir -p "$BACKUP_DIR"
    python3 -c '
import sqlite3, sys
dst = sqlite3.connect(sys.argv[2])
sqlite3.connect("file:" + sys.argv[1] + "?mode=ro", uri=True).backup(dst)
assert dst.execute("pragma integrity_check").fetchone()[0] == "ok"
' "$LIVE_DB" "$dest"
}

swap_to() {
    docker tag "music-minion:$1" music-minion:current
    (cd "$DEPLOY_DIR" && docker compose up -d --remove-orphans)
}

wait_healthy() {
    local s
    for _ in $(seq 1 $((HEALTH_TIMEOUT_S / 5))); do
        s=$(docker inspect -f '{{.State.Health.Status}}' music-minion-web 2>/dev/null || true)
        [ "$s" = healthy ] && return 0
        sleep 5
    done
    return 1
}

deploy() {
    local previous
    previous=$(docker image inspect -f '{{.Id}}' music-minion:current 2>/dev/null || true)
    [ -n "$previous" ] && docker tag music-minion:current music-minion:previous
    cp "$SRC_DIR/docker/pi-deployment/docker-compose.yml" "$DEPLOY_DIR/"

    echo "==> Starting music-minion:$TAG"
    swap_to "$TAG"
    if wait_healthy; then
        echo "$SHA" > "$DEPLOY_DIR/.deployed-sha"
        echo "==> Healthy: music-minion:$TAG is live at https://music.piserver:8443"
        return 0
    fi

    echo "!! music-minion:$TAG did not become healthy" >&2
    docker logs --tail 30 music-minion-web >&2 || true
    if [ -n "$previous" ]; then
        echo "!! Rolling back to the previous image (DB snapshot is in $BACKUP_DIR)" >&2
        swap_to previous
    fi
    return 1
}

build_image
snapshot_db
deploy
