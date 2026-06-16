#!/usr/bin/env bash
#
# e2e.sh — Run Maestro end-to-end tests against an Android emulator.
#
# Boots the `mm_test` AVD if it is not already running, (re)builds + installs
# the release APK with `expo run:android --variant release` unless --no-build
# is passed, then runs the Maestro flows in .maestro/.
#
# The release build inlines EXPO_PUBLIC_API_URL from .env, so tests hit the
# live piserver backend over Tailscale (host must be on the tailnet + Pi up).
#
# Usage:
#   ./scripts/e2e.sh                     # boot, build+install, run full suite
#   ./scripts/e2e.sh --no-build          # skip build, run against installed app
#   ./scripts/e2e.sh .maestro/00_launch.yml   # run a single flow (implies --no-build)
#
# Requires: Android SDK (emulator, adb, ~/Android/Sdk), Maestro CLI (~/.maestro/bin),
#           a built/installable Expo Android project.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

export ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
export PATH="$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$HOME/.maestro/bin"
export MAESTRO_CLI_NO_ANALYTICS=1
# Headless swiftshader emulators are slow to bring up the instrumentation
# driver; the 15s default times out. Also: kill any Metro/expo dev server
# before running — it competes for the device and causes launch flakiness.
export MAESTRO_DRIVER_STARTUP_TIMEOUT="${MAESTRO_DRIVER_STARTUP_TIMEOUT:-120000}"

AVD_NAME="mm_test"
EXPO_BIN="$PROJECT_DIR/../node_modules/.bin/expo"   # binary hoisted to monorepo root

# --- args ---------------------------------------------------------------------
DO_BUILD=1
FLOW_ARG=".maestro/"
for arg in "$@"; do
  case "$arg" in
    --no-build) DO_BUILD=0 ;;
    *.yml|*.yaml) FLOW_ARG="$arg"; DO_BUILD=0 ;;   # single flow → assume already installed
    *) echo "Unknown arg: $arg" >&2; exit 2 ;;
  esac
done

cd "$PROJECT_DIR"

# --- 1. ensure the emulator is running ----------------------------------------
# 4GB RAM is deliberate: with the default heap the headless emulator OOM-kills
# Maestro's on-device driver mid-flow (gRPC "UNAVAILABLE" / "tcp closed").
if ! adb devices | grep -q "emulator-"; then
  echo "▶ Booting emulator '$AVD_NAME' (4GB RAM, headless)..."
  emulator -avd "$AVD_NAME" -no-snapshot -no-boot-anim -no-window \
    -gpu swiftshader_indirect -memory 4096 -cores 4 &
  adb wait-for-device
  echo "  waiting for boot to complete..."
  until [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do sleep 2; done
else
  echo "✓ Emulator already running."
fi

# Disabling animations cuts flakiness and speeds up the run.
adb shell settings put global window_animation_scale 0 >/dev/null 2>&1 || true
adb shell settings put global transition_animation_scale 0 >/dev/null 2>&1 || true
adb shell settings put global animator_duration_scale 0 >/dev/null 2>&1 || true

# --- 2. build + install -------------------------------------------------------
if [ "$DO_BUILD" -eq 1 ]; then
  echo "▶ Building + installing release APK (expo run:android)..."
  ( cd "$PROJECT_DIR" && "$EXPO_BIN" run:android --variant release )
fi

# --- 3. run flows -------------------------------------------------------------
# Run each flow in its OWN maestro process. A single `maestro test .maestro/`
# reuses one driver session across flows and destabilizes on slow emulators;
# a fresh process per flow is far more reliable.
echo "▶ Running Maestro flows: $FLOW_ARG"
if [ -d "$FLOW_ARG" ]; then
  pass=0; fail=0; failed=""
  for flow in "$FLOW_ARG"/[0-9]*.yml; do
    name="$(basename "$flow")"
    if maestro test "$flow"; then echo "  ✓ $name"; pass=$((pass + 1))
    else echo "  ✗ $name"; fail=$((fail + 1)); failed="$failed $name"; fi
    sleep 3
  done
  echo "═══ $pass passed, $fail failed ═══${failed:+ FAILED:$failed}"
  [ "$fail" -eq 0 ]
else
  maestro test "$FLOW_ARG"
fi
