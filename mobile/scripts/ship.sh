#!/usr/bin/env bash
#
# ship.sh — Build + deploy the Music Minion mobile app (Expo / Android).
#
# This is a personal, sideloaded Android app. There is no Play Store
# submission step; we either build an internal APK and install it onto a
# USB/Wi-Fi connected device via adb, or we push an over-the-air (OTA) JS
# bundle update through EAS Update.
#
# Subcommands:
#   build      — eas build (internal apk), output to dist/. No install.
#   install    — adb install the most recent dist/ apk onto a connected device.
#   apk        — convenience: build then install (build + adb install).
#   ota        — eas update, push a new JS bundle to an existing channel.
#
# Usage:
#   ./scripts/ship.sh build   [--profile preview|production|development] [--remote]
#   ./scripts/ship.sh install [--profile preview|production|development]
#   ./scripts/ship.sh apk     [--profile preview|production|development] [--remote]
#   ./scripts/ship.sh ota     [--channel preview|production|development] [--message "msg"]
#
# Notes:
#   - Build profiles come from eas.json: development / preview / production.
#     preview + production both emit a sideloadable apk (buildType: "apk").
#     development is a dev-client debug build.
#   - OTA channels match the profile channels in eas.json: development,
#     preview, production.
#   - By default `build` runs `eas build --local` (compiles on this machine,
#     no EAS queue). Pass --remote to build on EAS servers instead.
#   - APK rebuilds are required when native deps / app.json native config
#     change. OTA is for JS/asset-only changes within the same runtimeVersion.
#     runtimeVersion policy is "appVersion" — bump app.json `version` to
#     intentionally break OTA compatibility with installed builds.
#   - Requires eas-cli (run via `npx eas-cli`) and a logged-in Expo account
#     (`eas login`). `install`/`apk` also require Android platform-tools (adb).

set -euo pipefail

# --- locate project root (parent of this script's dir) ------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

DIST_DIR="$PROJECT_DIR/dist"

# --- defaults -----------------------------------------------------------------
MODE="${1:-}"
PROFILE="preview"
CHANNEL="preview"
MESSAGE="OTA update $(date -u +%Y-%m-%dT%H:%M:%SZ)"
REMOTE=0

if [[ -z "$MODE" ]]; then
  echo "usage: ship.sh <build|install|apk|ota> [options]" >&2
  exit 64
fi
shift || true

# --- parse flags --------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="${2:?--profile needs a value}"; shift 2 ;;
    --channel) CHANNEL="${2:?--channel needs a value}"; shift 2 ;;
    --message) MESSAGE="${2:?--message needs a value}"; shift 2 ;;
    --remote)  REMOTE=1; shift ;;
    *) echo "unknown flag: $1" >&2; exit 64 ;;
  esac
done

# --- load env (EXPO_PUBLIC_* vars get inlined at build/bundle time) -----------
if [[ -f "$PROJECT_DIR/.env" ]]; then
  echo ">> Loading env from .env"
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.env"
  set +a
fi

# --- helpers ------------------------------------------------------------------
require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: missing required tool: $1" >&2
    echo "       (install it, then re-run: ship.sh $MODE)" >&2
    exit 69
  }
}

apk_path() { echo "$DIST_DIR/music-minion-$PROFILE.apk"; }

check_device() {
  require adb
  # Count devices in the "device" state (excludes "offline"/"unauthorized").
  local count
  count="$(adb devices | awk 'NR>1 && $2=="device" {c++} END {print c+0}')"
  if [[ "$count" -eq 0 ]]; then
    echo "ERROR: no Android device connected (adb sees 0 ready devices)." >&2
    echo "       Plug in via USB (enable USB debugging) or pair over Wi-Fi," >&2
    echo "       then verify with: adb devices" >&2
    exit 1
  fi
  echo ">> adb sees $count connected device(s)."
}

# --- actions ------------------------------------------------------------------
build_apk() {
  require npx
  mkdir -p "$DIST_DIR"
  local out; out="$(apk_path)"
  if [[ "$REMOTE" -eq 1 ]]; then
    echo ">> Building APK on EAS servers (profile=$PROFILE) ..."
    npx eas-cli build \
      --platform android \
      --profile "$PROFILE" \
      --non-interactive
    echo ">> Remote build queued. Download the APK from the EAS build page,"
    echo "   or re-run with: ship.sh install --profile $PROFILE"
  else
    echo ">> Building APK locally (profile=$PROFILE) -> $out"
    npx eas-cli build \
      --platform android \
      --profile "$PROFILE" \
      --non-interactive \
      --local \
      --output "$out"
    echo ">> Build complete: $out"
  fi
}

install_apk() {
  local out; out="$(apk_path)"
  if [[ ! -f "$out" ]]; then
    echo "ERROR: no APK at $out" >&2
    echo "       Build one first: ship.sh build --profile $PROFILE" >&2
    exit 1
  fi
  check_device
  echo ">> Installing $out onto connected device ..."
  adb install -r "$out"
  echo ">> APK installed."
}

push_ota() {
  require npx
  echo ">> Pushing OTA update (channel=$CHANNEL) ..."
  npx eas-cli update \
    --channel "$CHANNEL" \
    --message "$MESSAGE" \
    --non-interactive
  echo ">> OTA published. Clients on channel '$CHANNEL' pull it on next launch."
}

# --- dispatch -----------------------------------------------------------------
case "$MODE" in
  build)   build_apk ;;
  install) install_apk ;;
  apk)     build_apk && install_apk ;;
  ota)     push_ota ;;
  *) echo "unknown mode: $MODE (expected build|install|apk|ota)" >&2; exit 64 ;;
esac
