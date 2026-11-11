#!/bin/bash
# Runs ON the pi from a systemd timer: deploy GitHub main once CI passes.
#
# Each tick: ls-remote main; if it moved since the last commit we acted on,
# ask the GitHub API whether every check run on it succeeded. Pending → try
# again next tick. Failed CI or failed deploy → mark the commit handled so we
# don't retry it every tick (the next merge gets a fresh attempt).
#
# Acting on "main moved" rather than "live != main" keeps a manual
# deploy-to-pi.sh hotfix live until the next merge.
#
# Installed to ~/.local/bin/music-minion-autodeploy by
# docker/pi-deployment/systemd/install.sh, and refreshed after every deploy.
set -euo pipefail

REPO_SLUG=Andrewske/music-minion-cli
REPO_URL=https://github.com/$REPO_SLUG.git
MIRROR=/home/kevin/music-minion-src.git
BUILD_DIR=/home/kevin/music-minion-build
DEPLOY_DIR=/home/kevin/music-minion-deploy
HOST_CHECKOUT=/home/kevin/music-minion
LAST_MAIN=$DEPLOY_DIR/.last-main-sha
STATUS=$DEPLOY_DIR/autodeploy-status
LOCK=$DEPLOY_DIR/.deploy.lock

log() { echo "$(date -Is) $*"; }
record() { echo "$(date -Is) $1 ${2:0:7}" > "$STATUS"; echo "$2" > "$LAST_MAIN"; }

# success | pending | failure over GitHub Actions check runs only (other apps,
# e.g. Dependabot, don't gate). API errors (rate limit, network) read as pending.
ci_state() {
    curl -fsS -H "Accept: application/vnd.github+json" \
        "https://api.github.com/repos/$REPO_SLUG/commits/$1/check-runs?per_page=100" \
        2>/dev/null | jq -r '
        [.check_runs[] | select(.app.slug == "github-actions")] as $runs
        | if ($runs | length) == 0 then "pending"
        elif any($runs[]; .status != "completed") then "pending"
        elif all($runs[]; .conclusion == "success" or .conclusion == "skipped"
                 or .conclusion == "neutral") then "success"
        else "failure" end' 2>/dev/null || echo pending
}

export_tree() {
    [ -d "$MIRROR" ] || git clone -q --bare "$REPO_URL" "$MIRROR"
    git -C "$MIRROR" fetch -q origin "+refs/heads/main:refs/heads/main"
    rm -rf "$BUILD_DIR" && mkdir -p "$BUILD_DIR"
    git -C "$MIRROR" archive --format=tar "$1" | tar -x -C "$BUILD_DIR"
}

# The host-side clone runs the nightly metadata_cleanup; keep it on main too.
refresh_host_checkout() {
    git -C "$HOST_CHECKOUT" pull -q --ff-only \
        && (cd "$HOST_CHECKOUT" && ~/.local/bin/uv sync -q --frozen --no-dev) \
        || log "warning: could not refresh $HOST_CHECKOUT (deploy itself succeeded)"
}

deploy() {
    export_tree "$1"
    if "$BUILD_DIR/scripts/deploy-on-pi.sh" "$BUILD_DIR" "$1"; then
        install -m 755 "$BUILD_DIR/scripts/pi-autodeploy.sh" ~/.local/bin/music-minion-autodeploy
        record deployed "$1"
        refresh_host_checkout
    else
        record deploy-failed "$1"
        return 1
    fi
}

main() {
    local sha state
    sha=$(git ls-remote "$REPO_URL" refs/heads/main | cut -f1)
    [ -n "$sha" ] || { log "could not read main from $REPO_URL"; exit 0; }
    [ "$sha" = "$(cat "$LAST_MAIN" 2>/dev/null)" ] && exit 0

    state=$(ci_state "$sha")
    case "$state" in
        success) ;;
        failure) log "CI failed on ${sha:0:7}; not deploying"; record ci-failed "$sha"; exit 1 ;;
        *) log "waiting for CI on ${sha:0:7}"; exit 0 ;;
    esac

    log "CI passed on ${sha:0:7}; deploying"
    exec 9>"$LOCK"
    flock -w 600 9 || { log "deploy lock busy; retrying next tick"; exit 0; }
    deploy "$sha"
}

main "$@"
