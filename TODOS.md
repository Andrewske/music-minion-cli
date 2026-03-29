# TODOS

## SC Push Worker: Bounded retry for transient failures
**Priority:** Low
**Context:** The background SC push worker (Task 01 of concurrent-squishing-salamander) is fire-and-forget — if the SC API is temporarily down, pushes are silently lost. A bounded retry (e.g., retry once after 30s, then drop) would catch transient failures without adding unbounded complexity. The manual sync button (Task 04/05) serves as the user-facing escape hatch for reconciliation.
**Depends on:** SC push worker (web/backend/sc_push_worker.py) must exist first.
**Added:** 2026-03-17 via /plan-eng-review

## Android App: Waveform visualization for mobile player
**Priority:** P2/High
**Context:** Kevin rates this as high priority. wavesurfer.js (used in web) is web-only and has no direct React Native equivalent. Current plan ships a plain seek slider in v1. Options for a future implementation: (1) react-native-audio-waveform (limited, peaks-only), (2) custom react-native-skia canvas drawing waveform peaks from the existing `/tracks/{id}/waveform` backend endpoint, (3) expo-av waveform metering (live only, not static). The backend already returns waveform peak data — the hard part is the rendering, not the data.
**Effort:** L (human) → M (CC) — Skia canvas approach
**Depends on:** Phase 4 (RNTP player) must be complete first. Backend waveform endpoint already exists.
**Added:** 2026-03-18 via /plan-ceo-review

## Android App: Home screen widget (Now Playing + controls)
**Priority:** P3/Low
**Context:** Android home screen widget showing current track title + play/pause/skip. Runs in a separate process via RemoteViews — cannot use standard React Native components. Requires react-native-android-widget or native module. Add after the app is stable.
**Effort:** L (human) → M (CC)
**Depends on:** Phase 4 (RNTP player) must be complete first.
**Added:** 2026-03-18 via /plan-ceo-review

## Android App: Android Auto integration
**Priority:** P3/Low
**Context:** Car display + voice control for playback. Implements MediaBrowserServiceCompat interface. Requires separate app declaration, separate UI API (not standard RN components). For sideloading, can bypass Google's Play Store verification but setup is complex.
**Effort:** L (human) → ~3 hrs (CC)
**Depends on:** Phase 4 (RNTP player) must be complete. Android Auto builds on top of RNTP MediaSession.
**Added:** 2026-03-18 via /plan-ceo-review

## Android App: Offline audio cache
**Priority:** P2/Medium
**Context:** Download top-rated tracks locally to device for playback without Tailscale connectivity. RNTP supports local file playback natively. Needs: download queue UI, storage management (quota), cache invalidation (track updated on server), offline/online mode switching. Backend already streams files — this intercepts those streams and stores them locally via react-native-fs or expo-file-system.
**Effort:** L (human) → ~2 hrs (CC)
**Depends on:** Phase 4 (RNTP player) must be complete. Should be its own separate plan.
**Added:** 2026-03-18 via /plan-ceo-review

## Discovery: CLI command with full parity
**Priority:** P3/Low
**Context:** The discovery sync engine (`web/backend/discovery_sync.py`) runs from the web UI via FastAPI endpoints. A CLI command `music-minion discovery sync [--dry-run] [--limit N]` would allow running syncs from the terminal or cron. Implementation is a thin wrapper around `run_discovery_sync()` with progress output to stdout and a summary table showing artist distribution, tracks found, mixes routed. Integrate with the blessed UI command system.
**Effort:** S (human) → S (CC)
**Depends on:** Discovery sync feature must be complete and stable first.
**Added:** 2026-03-29 via /plan-ceo-review + /plan-eng-review

## Clean up `affects_global` column in playlist_comparison_history
**Priority:** P3/Low
**Context:** After the global comparison graph migration (graceful-snacking-seahorse), `affects_global` is always `False` for new rows. The column is dead weight — ~2KB for 1,956 booleans. Not causing harm, but misleading for anyone reading the schema. Fix requires SQLite table rebuild (CREATE new table, INSERT ... SELECT, DROP old, ALTER TABLE RENAME) + updating all INSERT statements that reference the column.
**Depends on:** graceful-snacking-seahorse must ship first.
**Effort:** M (human) → S (CC)
**Added:** 2026-03-18 via /plan-ceo-review
