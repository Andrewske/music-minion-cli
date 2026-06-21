# Authoring flows, testIDs, build path & advanced

## Flow inventory (`mobile/.maestro/`)

| File | Asserts | Notes |
|------|---------|-------|
| `00_launch.yml` | cold launch → `tab-home` visible | `extendedWaitUntil` 30 s for bundle load |
| `01_config_fallthrough.yml` | `clearState` → still lands Home | env URL fallback guard (gate unreachable) |
| `02_browse_play.yml` | search "the" → tap track → `player-track-title` | exercises search + playback |
| `03_comparison.yml` | pick playlist → picker disappears | non-destructive (no vote; avoids mutating ELO). Vote buttons sit below the scroll fold, so don't assert them |
| `04_organizer.yml` | create bucket → assign track | mildly mutates session state on backend |
| `config.yaml` | workspace config | `flows: ["*.yml"]` |

## Flow-authoring lessons

- Use `extendedWaitUntil { visible: { id }, timeout: 30000 }` after `launchApp` / network-gated taps.
  A bare `assertVisible` fires before render/fetch completes and flakes.
- Prefer `id:` selectors over `text:`. For "did we navigate?", assert `notVisible` on the prior
  screen's id rather than asserting a possibly-off-screen target.
- Keep flows **non-destructive** against the live backend where possible (don't cast votes).

## testID map (added to the app)

| File | testIDs |
|------|---------|
| `app/(tabs)/_layout.tsx` | `tab-home`, `tab-compare`, `tab-organize`, `tab-history`, `tab-settings` (via `tabBarButtonTestID`) |
| `app/setup.tsx` | `setup-url-input`, `setup-test-btn` |
| `app/(tabs)/index.tsx` | `home-search-input`; `track-card` (first row only) |
| `components/tracks/TrackCard.tsx` | forwards optional `testID` prop → Pressable |
| `components/comparison/VoteButtons.tsx` | `vote-a`, `vote-b` |
| `app/(tabs)/comparison.tsx` | `comparison-playlist-option` (first row) |
| `app/(tabs)/organizer/index.tsx` | `organizer-playlist-option` (first row) |
| `app/(tabs)/organizer/[sessionId].tsx` | `bucket-name-input`, `create-bucket-btn`, `track-row` (first) |
| `components/player/PlayerBar.tsx` | `player-bar`, `player-track-title` |

**List-row pattern:** put the testID on the first item only (`index === 0 ? 'x' : undefined`).
Maestro taps the first match; this avoids duplicate-id ambiguity.

## Build path (important nuances)

- Build via **`expo run:android --variant release`**, NOT eas / `ship.sh`, for local E2E. Compiles a
  standalone release APK (JS bundled, testIDs intact) and installs straight to the booted emulator.
  No EAS login, no Metro needed at runtime.
- The expo binary is **hoisted to the monorepo root**: `node_modules/.bin/expo` (npm workspaces).
  `npx expo` from the repo root misfires into a workspace-script lookup — call the binary directly,
  with cwd = `mobile/`.
- The release build **bakes `EXPO_PUBLIC_API_URL`** from `mobile/.env` into the bundle →
  `https://piserver.tail80eccb.ts.net:8446/api` (Tailscale serve → loopback :8642; trusted cert).
  Requires host on the tailnet + Pi up. If a build's JS bundle caches stale env, rebuild with gradle
  `--rerun-tasks`.
- **Consequence for tests:** with the URL baked in, the app skips the first-run **setup gate**
  entirely — that screen is unreachable in this build. There is no setup-gate flow; to test the real
  gate, build WITHOUT `EXPO_PUBLIC_API_URL`.

## Out of scope (potential future work)

- EAS Workflow CI (`.eas/workflows/e2e-test-android.yml` + `e2e-test` build profile, Maestro Cloud).
- Hermetic local backend via emulator `10.0.2.2` (run `music-minion --web`, drop the Pi dependency).
- Maestro Cloud parallel runs / device matrix.
