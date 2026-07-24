# Mobile App Completion — 35-Step Plan

> **Source:** conversation `f7ff62e8` (2026-06-02 23:06). Agent fanned out subagents to
> investigate mobile state, returned this plan, did **no work**. Goal: get the Expo Android
> app's **playlist-organizer** and **general track playback** working.
> Documented 2026-06-08.

**Baseline at time of planning:** main HEAD `30b370e`. Branch `worktree-mobile-app-p0`
was 2 ahead / 9 behind main (commits `6ed7ce9` SDK 52→55 + first APK build, `94e9890`
first Android audio).

---

## Phase 1: Consolidate branches (steps 1–7)

1. `rtk git fetch` + `rtk git log --oneline -10 main` — confirm main HEAD (`30b370e`), no new commits since investigation.
2. From main repo root: `rtk git diff main...worktree-mobile-app-p0 --stat` — re-confirm 19-file / 2-commit divergence before touching anything.
3. Check out worktree branch in its worktree: `cd .claude/worktrees/mobile-app-p0`, `rtk git status` — verify only `android/` + `app.json` stray prebuild artifacts untracked; delete them (`rm -rf android app.json` at worktree root, **NOT** `mobile/`).
4. Rebase worktree branch onto main: `rtk git rebase main` from inside worktree (2 ahead / 9 behind).
5. Resolve rebase conflicts — expect `package-lock.json` / `bun.lock` (regenerate via `npm install` / `bun install`, don't hand-merge) and possibly `shared/src/stores/createPlayerStore.ts`. Document each resolution.
6. After rebase: `rtk git log --oneline -5` to confirm `6ed7ce9` + `94e9890` sit on top of `30b370e`. Build-sanity: `cd mobile && npm install` then `npx tsc --noEmit`.
7. Merge worktree into main (`rtk git checkout main && rtk git merge --ff-only worktree-mobile-app-p0`), then prune dead worktrees: `rtk git worktree remove` the two `agent-*` worktrees + `rtk git branch -d worktree-agent-a0064b05 worktree-agent-aebd7873`.

## Phase 2: Fix API URL config (steps 8–12)

8. Read `mobile/.env` and `mobile/.env.example` — confirm committed default `EXPO_PUBLIC_API_URL=http://localhost:8642/api` + the Tailscale example form.
9. Determine actual piserver/backend Tailscale hostname (check docs/reference or ask user for `*.tailnet.ts.net` name — do **NOT** guess).
10. Read `mobile/hooks/useServerUrl.ts` fully — confirm AsyncStorage-first / env-fallback / setup-screen-gate precedence, so fix targets right layer.
11. Decide fix: working Tailscale default in `.env`, OR keep env empty + make `setup` screen mandatory first-run. Pick based on whether `.env` is gitignored (check `mobile/.gitignore`).
12. Apply fix; verify `mobile/app/setup.tsx` writes to AsyncStorage and that blank/`localhost` env falls through to setup gate instead of silently failing.

## Phase 3: Wire NowPlaying expanded sheet (steps 13–20)

13. Read `mobile/components/player/NowPlaying.tsx` end-to-end — catalog props, the `handleSeek` double-apply bug (`:55-58`), emoji artwork placeholder (`:69`).
14. Read `mobile/components/player/PlayerBar.tsx` — locate track-info area + "Phase 4 v2" comment (`:5`); identify where to attach expand trigger.
15. Choose sheet mechanism: RN `Modal`, `@gorhom/bottom-sheet`, or expo-router modal route. Check `mobile/package.json` for already-installed sheet libs before adding a dep.
16. Add expand state to `PlayerBar` (local `useState` or UI store), `onPress` on track-info touchable to open `NowPlaying`.
17. Render `NowPlaying` inside chosen sheet/modal, pass required props; add close/collapse handler (swipe-down or chevron).
18. **Fix `NowPlaying handleSeek` double-apply:** remove local `TrackPlayer.seekTo` OR the `seek()` POST — keep one path. Verify against web's `lastSeekAt` remote-seek detection in `syncState` so WS echo doesn't fight local seek.
19. Wire artwork: pass `getArtworkUrl(track.id)` (backend `/tracks/{id}/artwork`, `routers/tracks.py:151`) into `NowPlaying`'s image + RNTP `artwork` field in `usePlayer.ts` `setMediaItem` for lockscreen art.
20. `npx tsc --noEmit` + visual smoke: launch app, tap player bar, confirm sheet opens/closes, seek works without state thrash.

## Phase 4: Device QA — playback (#19) (steps 21–25)

21. Build + install on physical Android device over Tailscale (`eas build --local` or existing dev build → `adb install`); confirm app connects to backend via setup screen.
22. Test basic playback: search local track on home tab, tap play, confirm audio output + `PlayerBar` reflects playing state.
23. Test lockscreen/notification controls (play/pause/next/prev/seek from `services/playback.ts`) + background playback (audio continues backgrounded).
24. Test seek slider, scrobble fire at 50%/30s (verify backend `/tracks/{id}/scrobble` hit via logs), auto-advance at track end, bad-URL auto-skip (410 path).
25. Test cross-device sync: play on web, confirm mobile `usePlayer` "Playing elsewhere" state + that taking over transfers playback. Log Tailscale-latency buffer issues for RNTP tuning.

## Phase 5: Device QA — comparison (#20) + organizer (#21) (steps 26–31)

26. Comparison (#20): open comparison tab, pick playlist, test left/right swipe voting, optimistic next-pair, vote counter, progress bar, completion screen, haptics.
27. Comparison error recovery: kill network mid-vote, confirm graceful retry/no crash.
28. Organizer (#21): open organizer tab, pick `track_count > 0` playlist, confirm session creates/resumes + buckets render.
29. Organizer assignment flow: tap-to-assign (note first-bucket-only limitation), swipe-to-unassign (`TrackRow`), bucket create/move/shuffle/delete, Apply/Finalize/Discard.
30. Organizer state-across-backgrounding: assign tracks, background app, return — confirm session state persists (React Query cache + backend).
31. **Fix `[sessionId].tsx:29-33` double session-fetch** (re-key hook by `sessionId` or pass session through nav params) + guard `handleAssignTrack` with `isAssigning` to block double-tap dupes. Re-test.

## Phase 6: P2 polish (steps 32–35)

32. Share intent (#22): test Android SEND from browser (YT/Shorts/SoundCloud URL) via `expo-share-intent` into `useShareIntent.ts` → confirm import field auto-fills, cold-start + running.
33. EAS + deploy (#23): flesh out `eas.json` (appVersionSource, preview/production channels, OTA), add `expo-updates`/runtimeVersion to `app.json`, write `scripts/ship.sh` (build + adb-install / OTA), model on tracker-app.
34. Branding (#24): replace default Expo assets — 1024px app icon, Android adaptive icon, dark splash (#121212 bg, #7C4DFF purple) in `mobile/assets/` + `app.json`.
35. Offline resilience (#25): add offline UI states, connection-status indicator, manual-retry button, restored-connection toast on top of existing exponential-backoff WS in `useSyncWebSocket.ts`.

---

## Known bugs flagged

- `NowPlaying.tsx:55-58` — seek double-apply
- `[sessionId].tsx:29-33` — double session-fetch
- `handleAssignTrack` — no `isAssigning` guard → double-tap dupes

## Notes

- **Organizer = Phase 5 (steps 28–31)**, gated behind Phases 1–4 (branch merge + API config + playback QA must land first).
- Optional organizer parity work (bucket picker, emoji/rename UI, link UI) intentionally left out — fold into Phase 5 only if #21 QA demands.
