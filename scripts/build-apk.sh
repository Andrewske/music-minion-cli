#!/usr/bin/env bash
# Build a release APK of the mobile app and publish it for the in-app updater.
#
# Writes <out>/music-minion.apk and <out>/latest.json. The backend serves them
# at GET /api/app/apk and GET /api/app/latest from MUSIC_MINION_APP_UPDATES_DIR
# (default ~/.local/share/music-minion/app-updates, already volume-mounted
# into the pi container).
#
# Usage:
#   scripts/build-apk.sh                # build into mobile/dist/app-updates
#   scripts/build-apk.sh --upload       # build, then copy to the pi
#   scripts/build-apk.sh --out DIR      # build into DIR (e.g. on the pi itself)
#
# Options:
#   --upload        scp to $UPLOAD_HOST:$UPLOAD_DIR (piserver, app-updates dir)
#   --out DIR       local output directory
#   --rerun         force gradle --rerun-tasks (done automatically when .env changes)
#   --force         publish even if versionCode isn't newer than the last build
#
# Versioning: versionCode = `git rev-list --count HEAD`, versionName =
# "1.<count>+<sha>" (see mobile/app.config.js). Build from main (or a
# descendant of the last published commit) or Android refuses the downgrade.
#
# Signing: release builds use mobile/android/app/debug.keystore. The installed
# app was signed with it, so the cert fingerprint is pinned below; a different
# key would make every update fail to install.
set -euo pipefail

UPLOAD_HOST="${UPLOAD_HOST:-piserver}"
UPLOAD_DIR="${UPLOAD_DIR:-/home/kevin/.local/share/music-minion/app-updates}"
EXPECTED_CERT_SHA256="FA:C6:17:45:DC:09:03:78:6F:B9:ED:E6:2A:96:2B:39:9F:73:48:F0:BB:6F:89:9B:83:32:66:75:91:03:3B:9C"
APK_NAME=music-minion.apk
MANIFEST_NAME=latest.json
CHANGELOG_FALLBACK_COUNT=20

REPO="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
MOBILE="$REPO/mobile"
ANDROID="$MOBILE/android"
OUT="$MOBILE/dist/app-updates"
UPLOAD=0
RERUN=0
FORCE=0

die() { echo "error: $*" >&2; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --upload) UPLOAD=1; shift ;;
        --out) OUT="${2:?--out needs a directory}"; shift 2 ;;
        --rerun) RERUN=1; shift ;;
        --force) FORCE=1; shift ;;
        -h|--help) sed -n '2,26p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) die "unknown option: $1 (see --help)" ;;
    esac
done

cd "$REPO"
SHA=$(git rev-parse --short HEAD)
VERSION_CODE=$(git rev-list --count HEAD)
VERSION_NAME="1.$VERSION_CODE+$SHA"
if [ -n "$(git status --porcelain --untracked-files=no -- mobile shared)" ]; then
    echo "warning: uncommitted changes in mobile/ or shared/ are baked into this build" >&2
    VERSION_NAME="$VERSION_NAME-dirty"
fi
export MM_VERSION_CODE="$VERSION_CODE" MM_VERSION_NAME="$VERSION_NAME"
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"

# EXPO_PUBLIC_* values (the backend URL) are inlined into the JS bundle.
if [ -f "$MOBILE/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$MOBILE/.env"
    set +a
fi

# Prints the previous build's manifest (the pi's when uploading, else local).
previous_manifest() {
    local remote=""
    if [ "$UPLOAD" -eq 1 ]; then
        remote=$(ssh "$UPLOAD_HOST" "cat '$UPLOAD_DIR/$MANIFEST_NAME' 2>/dev/null" || true)
    fi
    if [ -n "$remote" ]; then
        echo "$remote"
    elif [ -f "$OUT/$MANIFEST_NAME" ]; then
        cat "$OUT/$MANIFEST_NAME"
    fi
}

json_field() {  # json_field <field>  (reads JSON on stdin, prints "" if absent)
    node -e '
        let s = ""; process.stdin.on("data", (d) => (s += d)).on("end", () => {
            try { const v = JSON.parse(s)[process.argv[1]]; console.log(v ?? ""); }
            catch { console.log(""); }
        });' "$1"
}

check_version_is_newer() {
    local prev_code
    prev_code=$(json_field versionCode <<<"$PREVIOUS")
    [ -z "$prev_code" ] && return 0
    if [ "$VERSION_CODE" -le "$prev_code" ] && [ "$FORCE" -eq 0 ]; then
        die "versionCode $VERSION_CODE is not newer than the published $prev_code (build from main, or pass --force)"
    fi
}

# Commit subjects touching mobile/ or shared/ since the previous build.
changelog() {
    local prev_sha
    prev_sha=$(json_field sha <<<"$PREVIOUS")
    if [ -n "$prev_sha" ] && git merge-base --is-ancestor "$prev_sha" HEAD 2>/dev/null; then
        git log --no-merges --format=%s "$prev_sha..HEAD" -- mobile shared
    else
        git log --no-merges --format=%s -n "$CHANGELOG_FALLBACK_COUNT" -- mobile shared
    fi
}

check_keystore() {
    local keystore="$ANDROID/app/debug.keystore" fingerprint
    [ -f "$keystore" ] || die "missing $keystore (release builds must be signed with it)"
    fingerprint=$(keytool -list -v -keystore "$keystore" -storepass android 2>/dev/null \
        | awk '/SHA256:/ {print $2; exit}')
    [ "$fingerprint" = "$EXPECTED_CERT_SHA256" ] \
        || die "debug.keystore fingerprint $fingerprint != pinned $EXPECTED_CERT_SHA256; updates would not install"
}

# Gradle doesn't track .env, so a changed backend URL needs --rerun-tasks.
gradle_rerun_flag() {
    local stamp="$ANDROID/.mm-env-hash" current
    current=$(env | grep '^EXPO_PUBLIC_' | sort | sha256sum | cut -d' ' -f1)
    if [ "$RERUN" -eq 1 ] || [ ! -f "$stamp" ] || [ "$(cat "$stamp")" != "$current" ]; then
        echo "--rerun-tasks"
    fi
    echo "$current" >"$stamp.next"
}

build_apk() {
    echo "==> Prebuild (versionCode $VERSION_CODE, versionName $VERSION_NAME)"
    (cd "$MOBILE" && npx expo prebuild --platform android --no-install >/dev/null)
    check_keystore
    local rerun
    rerun=$(gradle_rerun_flag)
    echo "==> gradle assembleRelease ${rerun:-(incremental)}"
    # shellcheck disable=SC2086
    (cd "$ANDROID" && ./gradlew app:assembleRelease $rerun)
    mv "$ANDROID/.mm-env-hash.next" "$ANDROID/.mm-env-hash"
}

write_manifest() {
    local apk="$1" log="$2"
    local digest
    digest=$(sha256sum "$apk" | cut -d' ' -f1)
    MM_SHA="$SHA" MM_APK="$apk" MM_DIGEST="$digest" MM_LOG="$log" node -e '
        const fs = require("fs");
        const apk = process.env.MM_APK;
        const manifest = {
            versionCode: Number(process.env.MM_VERSION_CODE),
            versionName: process.env.MM_VERSION_NAME,
            sha: process.env.MM_SHA,
            built_at: new Date().toISOString(),
            apk_size: fs.statSync(apk).size,
            apk_sha256: process.env.MM_DIGEST,
            changelog: process.env.MM_LOG.split("\n").filter(Boolean),
        };
        process.stdout.write(JSON.stringify(manifest, null, 2) + "\n");'
}

publish_local() {
    local built="$ANDROID/app/build/outputs/apk/release/app-release.apk"
    [ -f "$built" ] || die "gradle finished but $built is missing"
    mkdir -p "$OUT"
    cp "$built" "$OUT/.$APK_NAME.tmp" && mv "$OUT/.$APK_NAME.tmp" "$OUT/$APK_NAME"
    # Manifest last, so it never points at an APK that isn't there yet.
    write_manifest "$OUT/$APK_NAME" "$(changelog)" >"$OUT/.$MANIFEST_NAME.tmp"
    mv "$OUT/.$MANIFEST_NAME.tmp" "$OUT/$MANIFEST_NAME"
    echo "==> Wrote $OUT/$APK_NAME and $OUT/$MANIFEST_NAME"
}

upload() {
    echo "==> Uploading to $UPLOAD_HOST:$UPLOAD_DIR"
    ssh "$UPLOAD_HOST" "mkdir -p '$UPLOAD_DIR'"
    scp -q "$OUT/$APK_NAME" "$UPLOAD_HOST:$UPLOAD_DIR/.$APK_NAME.tmp"
    scp -q "$OUT/$MANIFEST_NAME" "$UPLOAD_HOST:$UPLOAD_DIR/.$MANIFEST_NAME.tmp"
    ssh "$UPLOAD_HOST" "cd '$UPLOAD_DIR' && mv .$APK_NAME.tmp $APK_NAME && mv .$MANIFEST_NAME.tmp $MANIFEST_NAME"
}

PREVIOUS=$(previous_manifest)
check_version_is_newer
build_apk
publish_local
[ "$UPLOAD" -eq 1 ] && upload
echo "==> Published $VERSION_NAME (versionCode $VERSION_CODE)"
