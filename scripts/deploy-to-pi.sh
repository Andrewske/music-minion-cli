#!/bin/bash
# Deploy HEAD to the pi: build music-minion:<sha> from a clean `git archive`,
# snapshot the DB, swap :current, and roll back if /health doesn't come up.
#
# Ships the committed HEAD only; uncommitted changes never leave this machine.
# Pi layout: ~/music-minion-deploy holds docker-compose.yml, config.toml, .env
# (config and secrets live only on the pi). ~/music-minion-build is scratch.
set -euo pipefail

PI=piserver
BUILD_DIR=/home/kevin/music-minion-build
DEPLOY_DIR=/home/kevin/music-minion-deploy
LIVE_DB=/home/kevin/.local/share/music-minion/music_minion.db
BACKUP_DIR=/home/kevin/backups/music-minion
HEALTH_TIMEOUT_S=120

cd "$(git rev-parse --show-toplevel)"
SHA=$(git rev-parse --short HEAD)
[ -z "$(git status --porcelain --untracked-files=no)" ] \
    || echo "warning: uncommitted changes are NOT deployed (shipping $SHA)"

ship_source() {
    echo "==> Shipping $SHA to $PI:$BUILD_DIR"
    git archive --format=tar HEAD \
        | ssh "$PI" "rm -rf $BUILD_DIR && mkdir -p $BUILD_DIR && tar -x -C $BUILD_DIR"
}

build_image() {
    echo "==> Building music-minion:$SHA on $PI"
    ssh "$PI" "docker build -q -t music-minion:$SHA $BUILD_DIR"
}

snapshot_db() {
    local dest="$BACKUP_DIR/pi-predeploy-$SHA-$(date +%Y%m%d-%H%M%S).db"
    echo "==> Snapshotting DB to $dest"
    ssh "$PI" "mkdir -p $BACKUP_DIR && python3 -c '
import sqlite3, sys
dst = sqlite3.connect(sys.argv[2])
sqlite3.connect(\"file:\" + sys.argv[1] + \"?mode=ro\", uri=True).backup(dst)
assert dst.execute(\"pragma integrity_check\").fetchone()[0] == \"ok\"
' $LIVE_DB $dest"
}

swap_to() {
    ssh "$PI" "docker tag music-minion:$1 music-minion:current \
        && cd $DEPLOY_DIR && docker compose up -d --remove-orphans"
}

wait_healthy() {
    ssh "$PI" "for i in \$(seq 1 $((HEALTH_TIMEOUT_S / 5))); do
        s=\$(docker inspect -f '{{.State.Health.Status}}' music-minion-web 2>/dev/null)
        [ \"\$s\" = healthy ] && exit 0
        sleep 5
    done; exit 1"
}

deploy() {
    local previous
    previous=$(ssh "$PI" "docker image inspect -f '{{.Id}}' music-minion:current 2>/dev/null" || true)
    [ -n "$previous" ] && ssh "$PI" "docker tag music-minion:current music-minion:previous"
    ssh "$PI" "cp $BUILD_DIR/docker/pi-deployment/docker-compose.yml $DEPLOY_DIR/"

    echo "==> Starting music-minion:$SHA"
    swap_to "$SHA"
    if wait_healthy; then
        echo "==> Healthy: music-minion:$SHA is live at https://music.piserver:8443"
        return 0
    fi

    echo "!! music-minion:$SHA did not become healthy" >&2
    ssh "$PI" "docker logs --tail 30 music-minion-web" >&2 || true
    if [ -n "$previous" ]; then
        echo "!! Rolling back to the previous image (DB snapshot is in $BACKUP_DIR)" >&2
        swap_to previous
    fi
    return 1
}

ship_source
build_image
snapshot_db
deploy
