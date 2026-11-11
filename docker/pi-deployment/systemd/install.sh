#!/bin/bash
# One-time setup, run ON the pi from a source tree:
#   docker/pi-deployment/systemd/install.sh
# Seeds .last-main-sha with current main so the first tick doesn't redeploy it.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
DEPLOY_DIR=/home/kevin/music-minion-deploy
UNIT_DIR=~/.config/systemd/user

install -m 755 "$ROOT/scripts/pi-autodeploy.sh" ~/.local/bin/music-minion-autodeploy
mkdir -p "$UNIT_DIR"
install -m 644 "$HERE"/music-minion-autodeploy.{service,timer} "$UNIT_DIR/"

# Without a seed, the first tick would wait forever on a pre-CI commit.
# Assumes whatever is live already matches main (true right after a deploy).
if [ ! -f "$DEPLOY_DIR/.last-main-sha" ]; then
    git ls-remote https://github.com/Andrewske/music-minion-cli.git refs/heads/main \
        | cut -f1 > "$DEPLOY_DIR/.last-main-sha"
fi

systemctl --user daemon-reload
systemctl --user enable --now music-minion-autodeploy.timer
systemctl --user list-timers music-minion-autodeploy.timer --no-pager
