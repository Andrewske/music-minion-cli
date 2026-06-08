#!/usr/bin/env bash
#
# ship.sh — Build + deploy the Music Minion mobile app.
#
# This is a personal, sideloaded Android app. There is no Play Store
# submission step; we either build an APK and install it onto a USB/Wi-Fi
# connected device via adb, or we push an over-the-air (OTA) JS bundle
# update through EAS Update.
#
# Two modes:
#   apk    — eas build (internal apk) then adb install onto a connected device
#   ota    — eas update, push a new JS bundle to an existing channel
#
# Usage:
#   ./scripts/ship.sh apk [--profile preview|production]
#   ./scripts/ship.sh ota [--channel preview|production] [--message "msg"]
#
# Notes:
#   - APK rebuilds are required when native deps / app.json native config
#     change. OTA is for JS/asset-only changes within the same runtimeVersion
#     (runtimeVersion policy is "appVersion" — bump app.json version to break
#     OTA compatibility intentionally).
#   - Requires the eas-cli and a logged-in Expo account (eas login).

set -euo pipefail

# --- locate project root (parent of this script's dir) ------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# --- defaults -----------------------------------------------------------------
MODE="${1:-}"
PROFILE="preview"
CHANNEL="preview"
MESSAGE="OTA update $(date -u +%Y-%m-%dT%H:%M:%SZ)"

if [[ -z "$MODE" ]]; then
  echo "usage: ship.sh <apk|ota> [options]" >&2
  exit 64
fi
shift || true

# --- parse flags --------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --channel) CHANNEL="$2"; shift 2 ;;
    --message) MESSAGE="$2"; shift 2 ;;
    *) echo "unknown flag: $1" >&2; exit 64 ;;
  esac
done

# --- tool checks --------------------------------------------------------------
require() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing required tool: $1" >&2; exit 69; }
}

build_apk() {
  require npx
  echo ">> Building internal APK (profile=$PROFILE) ..."
  # --local builds on this machine; drop --local to build on EAS servers.
  npx eas-cli build \
    --platform android \
    --profile "$PROFILE" \
    --non-interactive \
    --local \
    --output "$PROJECT_DIR/dist/music-minion-$PROFILE.apk"

  echo ">> Installing onto connected device via adb ..."
  require adb
  adb wait-for-device
  adb install -r "$PROJECT_DIR/dist/music-minion-$PROFILE.apk"
  echo ">> APK installed."
}

push_ota() {
  require npx
  echo ">> Pushing OTA update (channel=$CHANNEL) ..."
  npx eas-cli update \
    --channel "$CHANNEL" \
    --message "$MESSAGE" \
    --non-interactive
  echo ">> OTA update published. Clients on channel '$CHANNEL' will pull on next launch."
}

# --- dispatch -----------------------------------------------------------------
case "$MODE" in
  apk) build_apk ;;
  ota) push_ota ;;
  *) echo "unknown mode: $MODE (expected 'apk' or 'ota')" >&2; exit 64 ;;
esac
