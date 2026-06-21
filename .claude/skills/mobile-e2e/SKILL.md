---
name: mobile-e2e
description: "Run and E2E-test the Music Minion Expo mobile app on a local Android emulator with Maestro. Covers the e2e.sh runner, emulator boot/driver gotchas, flow authoring, testIDs, and a troubleshooting cheat-sheet. Use when running the mobile app locally, writing or debugging Maestro flows, booting the Android emulator, or diagnosing test driver failures. Triggers on 'run mobile app', 'e2e', 'maestro', 'android emulator', 'mobile test', '.maestro', 'emulator OOM', 'AndroidDriverTimeout'."
---

# Music Minion Mobile — Local Run & Maestro E2E

Maestro drives the real Expo app on a local Android emulator (Playwright-style, native).
Runner `mobile/scripts/e2e.sh` boots the emulator → builds/installs a release APK → runs flows.
Local-only (no CI). Tests hit the **live piserver backend** over Tailscale.

## Quick start

```sh
cd mobile
./scripts/e2e.sh                          # boot + build/install + run full suite
./scripts/e2e.sh --no-build               # skip build, run against installed app (fast iterate)
./scripts/e2e.sh .maestro/00_launch.yml   # single flow (implies --no-build)
maestro studio                            # live UI hierarchy inspector — confirm testIDs resolve
```

Requires: host on the tailnet + Pi up (backend URL is baked into the release build). `~/.maestro/bin`
must be on PATH (it is **not** by default). First-time machine? See [reference/setup.md](reference/setup.md).

## The 4 gotchas (the reason this skill exists)

1. **Emulator MUST boot with `-memory 4096`.** Default heap → Android OOM-kills Maestro's on-device
   driver mid-flow → every flow fails with gRPC `UNAVAILABLE` / `IOException: tcp closed`. This was
   the single biggest blocker; 4 GB makes it rock-solid.
2. **`MAESTRO_DRIVER_STARTUP_TIMEOUT=120000`** — headless swiftshader is slow to start the
   instrumentation driver; the 15 s default throws `AndroidDriverTimeoutException`.
3. **One `maestro test <file>` process PER flow.** `maestro test .maestro/` reuses a single driver
   session across flows and destabilizes. `e2e.sh` loops per-file with `sleep 3` between.
4. **Disable animations** before running: `adb shell settings put global window_animation_scale 0`
   (also `transition_animation_scale`, `animator_duration_scale`).

Env that `e2e.sh` sets internally:
```sh
export ANDROID_HOME=$HOME/Android/Sdk
export PATH="$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$HOME/.maestro/bin"
export MAESTRO_CLI_NO_ANALYTICS=1
export MAESTRO_DRIVER_STARTUP_TIMEOUT=120000
```

## Emulator boot/kill (headless, KVM, 4 GB)

```sh
emulator -avd mm_test -no-snapshot -no-boot-anim -no-window \
  -gpu swiftshader_indirect -memory 4096 -cores 4 &
adb wait-for-device
until [ "$(adb shell getprop sys.boot_completed | tr -d '\r')" = "1" ]; do sleep 2; done
# done:
adb emu kill        # or: pkill -f qemu-system-x86_64
```

## Troubleshooting cheat-sheet

| Symptom | Cause / fix |
|---------|-------------|
| `AndroidDriverTimeoutException` | bump `MAESTRO_DRIVER_STARTUP_TIMEOUT`; ensure emulator booted |
| gRPC `UNAVAILABLE` / `tcp closed` mid-flow | emulator OOM — boot with `-memory 4096`; run flows per-process |
| "Unable to launch app" cascade after first flow | driver session reuse — one process per flow; `adb kill-server && adb start-server` to reset |
| All flows fail right after `adb kill-server` | device not ready — `adb wait-for-device` + check `sys.boot_completed=1` first |
| `track-card`/playlist option never appears | backend down or Tailscale off — `adb shell curl https://piserver.tail80eccb.ts.net:8446/api/health` |
| setup screen never shows | expected — env URL baked into release build (gate unreachable) |

## Key file paths

```
mobile/scripts/e2e.sh        # runner (boot + build + run)
mobile/scripts/ship.sh       # existing build/install/OTA helper (EAS path — NOT used for E2E)
mobile/.maestro/*.yml        # 5 flows + config.yaml
mobile/.env                  # EXPO_PUBLIC_API_URL (baked into release bundle at build)
mobile/eas.json              # build profiles (development/preview/production)
```

## Deep dives

- **Adding/debugging flows, testID map, build-path nuances, advanced (CI/Cloud/hermetic backend):**
  [reference/authoring-flows.md](reference/authoring-flows.md)
- **One-time machine setup (SDK / Java / cmdline-tools / AVD / Maestro install):**
  [reference/setup.md](reference/setup.md)
- **Project memory context:** `project_mobile_e2e_maestro`, `project_mobile_backend_url`
