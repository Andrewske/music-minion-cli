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

## Discovery: Audit `discovery_tracks.status` enum drift
**Priority:** P3/Low
**Context:** `get_seen_track_ids` (`web/backend/queries/discovery.py:172`) hardcodes 4 status values: `'liked'`, `'dismissed'`, `'in_playlist'`, `'unseen'`. If a 5th status is ever added (e.g., `'snoozed'`, `'maybe'`) and the function isn't updated, those tracks will silently be misclassified — likely treated as eligible for fresh fetch when they shouldn't be, or vice versa. Fix options: (1) add a SQLite CHECK constraint pinning allowed values (requires table rebuild via INSERT/DROP/RENAME hack), (2) extract the set of "classified" statuses to a single module-level constant + add a comment in the status column docstring pointing to it.
**Effort:** S (human) → XS (CC)
**Depends on:** nothing
**Added:** 2026-04-26 via /plan-eng-review

## Discovery: Investigate stuck `active` `bucket_sessions`
**Priority:** P2/Medium
**Context:** During the reposts playlist nuke, found 17 `bucket_sessions` rows with `status='active'` across various playlists. The active session for the reposts playlist (id=26) was finalized via `/api/buckets/sessions/<id>/finalize`, but the other 16 likely indicate a UI flow that never auto-finalizes — sessions get created on entry to the Playlist Organizer, but never get closed on tab close, navigation away, or completion. Next refresh on any of those playlists will partial-refill (preserving unassigned tracks) instead of full-replace, which may be unexpected. Investigation: (a) when does the frontend call finalize? (b) is there an idle-timeout mechanism? (c) should the backend auto-finalize on session age?
**Effort:** M (human) → S (CC) — investigation + fix
**Depends on:** nothing
**Added:** 2026-04-26 via /plan-eng-review

## Discovery: DB-only repost build path
**Priority:** P2/Medium
**Context:** With `sync_followings_reposts` (the feed-noise daemon) continuously populating `discovery_track_reposters` for every following, `run_discovery_sync` no longer needs to call the SC API to fetch reposts — the data already lives in the DB. A DB-only path would: (a) save ~30s and ~200 API calls per sync, (b) eliminate 429 risk during sync, (c) simplify the orchestrator. Tradeoff: changes adaptive cadence behavior (last_checked currently bumps when sync fetches), shifts metric semantics (`tracks_fetched`/`artists_checked` lose meaning), and would need a careful migration. Revisit after 1–2 weeks of post-fix data to confirm Bug A's fix produced the expected fresh fetches before deciding to remove the API path.
**Effort:** M (human) → ~30min (CC)
**Depends on:** Bug A fix lands first (current PR). Validate API path works before removing it.
**Added:** 2026-04-26 via /plan-eng-review
