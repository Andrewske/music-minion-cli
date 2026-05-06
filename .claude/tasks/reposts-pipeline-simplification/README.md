# Reposts Pipeline Simplification

## Overview

Second-pass simplification of the reposts discovery pipeline. Replace the multi-step path (`_fetch_all_reposts` → filter → duration split → slot caps → chronological select → backfill) with a single ranked SQL query (`get_repost_candidates`) over already-populated DB tables (`discovery_track_reposters`, `discovery_tracks`, `discovery_artists`), plus a small Python `apply_per_artist_cap` helper. Three call sites: reposts (short, recent), deep (short, 7–90d), mixes (long). Add a 24h cron on Pi and funnel telemetry. Net: ~400 lines lighter, true per-artist cap (every reposter, not just primary), no SC API call from sync.

Source: `/home/kevin/.claude/plans/reposts-pipeline-simplification.md`. Decisions locked 2026-04-27.

## Task Sequence

1. [01-add-repost-candidates-query.md](./01-add-repost-candidates-query.md) — New `get_repost_candidates` SQL with per-artist cap window function
2. [02-rewrite-prepare-for-sync.md](./02-rewrite-prepare-for-sync.md) — Return `(target_count, kept_sc_ids)` natively
3. [03-extend-sync-log-telemetry.md](./03-extend-sync-log-telemetry.md) — Funnel columns (#14): candidates_returned, deep_candidates_returned, kept_count
4. [04-rewrite-run-discovery-sync.md](./04-rewrite-run-discovery-sync.md) — Slim main pipeline, add deep playlist push
5. [05-delete-dead-code.md](./05-delete-dead-code.md) — Remove ~400 lines of superseded helpers
6. [06-add-tests.md](./06-add-tests.md) — New test classes + migrate existing
7. [07-deploy-deep-playlist-cron.md](./07-deploy-deep-playlist-cron.md) — Deploy, seed deep playlist, install cron, verify

Tasks 01/02/03 are independent (different functions or different parts of the file). 04 depends on all three. 05 depends on 04 (deletion of helpers no longer called). 06 depends on 01/02/04/05. 07 depends on 06.

## Success Criteria

End-to-end (run after Step 7 deploy):

- A. `POST /api/discovery/sync` produces 100 tracks in playlist 26
- B. Top of playlist sorted by descending reposter_count
- C. Zero overlap with owned tracks (other playlists + loved)
- D. Per-artist cap ≤ 5 across whole playlist
- E. Deep playlist populated, 7–90 day window, distinct from main reposts
- F. Cron fires at 6am, log entry in `/var/log/discovery-sync.log`

Local verification (Steps 1–6):
- `rtk uv run pytest tests/test_feed_sync.py -q` green
- `rtk uv run ruff check web/backend/` clean
- No non-test callers of deleted helpers (grep verification in Step 5)

## Dependencies

- **Already live:** previous fix (`e97e7e3`, `1ef1992`, `496b6bd`) on Pi — feed worker `sync_followings_reposts` populating `discovery_track_reposters` correctly.
- **Already populated:** `discovery_artists.in_top_200`, `hit_rate`, `ranking`.
- **Reused, no change:** `_push_to_sc_playlist`, `_update_discovery_feedback`.
- **Operational, manual on Pi:** create empty deep SC playlist via SC web UI, capture id, insert `playlists` row.

## Out of Scope

- Dropping legacy `tracks_fetched`/`artists_checked`/`tracks_new`/`tracks_skipped` columns — follow-up after ≥1 week (TODO E)
- Stuck active `bucket_sessions` — separate UX bug
- Adaptive cadence on feed worker — feed worker stays as-is
- `get_user_reposts` retry/backoff — unchanged

(Mixes playlist DB-only treatment was originally TODO D; folded into this PR via parameterized `get_repost_candidates`.)
