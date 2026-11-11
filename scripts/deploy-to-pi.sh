#!/bin/bash
# Manual deploy of the local HEAD to the pi. Main deploys automatically
# (scripts/pi-autodeploy.sh), so use this for hotfixes or to ship a branch.
#
# Ships the committed HEAD only; uncommitted changes never leave this machine.
# The pi does the build/snapshot/swap itself (scripts/deploy-on-pi.sh), under
# the same lock the autodeploy timer takes so the two never overlap.
set -euo pipefail

PI=piserver
BUILD_DIR=/home/kevin/music-minion-build
LOCK=/home/kevin/music-minion-deploy/.deploy.lock

cd "$(git rev-parse --show-toplevel)"
SHA=$(git rev-parse HEAD)
[ -z "$(git status --porcelain --untracked-files=no)" ] \
    || echo "warning: uncommitted changes are NOT deployed (shipping ${SHA:0:7})"

echo "==> Shipping ${SHA:0:7} to $PI:$BUILD_DIR"
git archive --format=tar HEAD | ssh "$PI" "flock -w 600 $LOCK sh -c '
    rm -rf $BUILD_DIR && mkdir -p $BUILD_DIR && tar -x -C $BUILD_DIR \
    && $BUILD_DIR/scripts/deploy-on-pi.sh $BUILD_DIR $SHA'"
