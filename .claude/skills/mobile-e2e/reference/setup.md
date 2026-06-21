# One-time machine setup

Everything below was done once on the dev machine (2026-06-16). Only needed on a fresh host.

## Environment inventory

| Tool | Location / value | Notes |
|------|------------------|-------|
| Android SDK | `~/Android/Sdk` (`ANDROID_HOME`) | adb, emulator binaries present |
| Java | OpenJDK 17 | required by Maestro |
| cmdline-tools | `~/Android/Sdk/cmdline-tools/latest` | gives `avdmanager` / `sdkmanager` |
| System image | `system-images;android-37.0;google_apis_playstore_ps16k;x86_64` | KVM available |
| AVD | `mm_test` (pixel_6 device profile) | created via avdmanager |
| Maestro CLI | `~/.maestro/bin/maestro` (v2.6.1) | **NOT on PATH** — add `~/.maestro/bin` |

## Install commands

```sh
# Maestro CLI → installs to ~/.maestro/bin
curl -fsSL https://get.maestro.mobile.dev -o /tmp/m.sh && bash /tmp/m.sh

# cmdline-tools (if avdmanager missing): unzip commandlinetools-linux into
# ~/Android/Sdk/cmdline-tools/latest/, then self-update.
# NOTE: an old cmdline-tools build only parses SDK XML v3, but the android-37
# image is v4 — you MUST self-update or sdkmanager can't see the image.
sdkmanager "cmdline-tools;latest"

# Create the AVD (ABI is x86_64; confirm available images with: sdkmanager --list_installed)
avdmanager create avd -n mm_test \
  -k "system-images;android-37.0;google_apis_playstore_ps16k;x86_64" --device pixel_6
```

KVM is required for usable performance (`-gpu swiftshader_indirect` headless). Confirm `/dev/kvm`
exists and is accessible by the user.
