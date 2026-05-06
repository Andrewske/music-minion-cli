---
task: 06-add-tests
status: pending
depends: [01-add-repost-candidates-query, 02-rewrite-prepare-for-sync, 04-rewrite-run-discovery-sync, 05-delete-dead-code]
files:
  - path: tests/test_feed_sync.py
    action: modify
---

# Test Suite for New Pipeline

## Context

Replace tests for deleted helpers with focused coverage of `get_repost_candidates`, `apply_per_artist_cap`, slim `run_discovery_sync` (reposts + deep + mixes), and rewritten `prepare_for_sync` (incl. dry_run).

## Files to Modify/Create

- `tests/test_feed_sync.py` (modify) — add 4 new test classes, migrate/delete 6 existing ones

## Implementation Details

**Add new test classes:**

1. **`TestGetRepostCandidates`** — `web/backend/queries/discovery.py::get_repost_candidates`
   - `test_multi_reposter_ranking`: 2 tracks both top-200; one has 3 reposters, one has 1. 3-reposter sorts first.
   - `test_owned_exclusion_other_playlist`: track in another playlist not in result.
   - `test_owned_exclusion_loved`: track rated 'love' not in result.
   - `test_status_excludes_liked_dismissed`: status='liked' and status='dismissed' excluded; status='in_playlist' (legacy) IS still returned.
   - `test_duration_filter_default`: tracks 60s and 700s excluded; 200s included (default 2–10 min).
   - `test_duration_filter_mixes`: with `duration_min_ms=600_000, duration_max_ms=7_200_000`, 700s and 1800s included; 200s excluded.
   - `test_window_days`: tracks reposted today; `window_days_min=7` returns 0; `window_days_min=0` returns them.
   - `test_kept_exclusion`: passing `exclude_sc_ids={...}` drops those.
   - `test_reposter_artist_ids_aggregated`: track with 2 reposters has both artist ids in `reposter_artist_ids` JSON.
   - `test_null_reposted_excluded`: NULL `reposted_at` rows not returned.

2. **`TestApplyPerArtistCap`** — `web/backend/queries/discovery.py::apply_per_artist_cap`
   - `test_cap_per_artist`: 8 candidates all reposted by artist X. Cap=5 → 5 returned.
   - `test_cap_target_truncates`: 100 candidates, all distinct artists. target=10 → 10 returned (cap not hit).
   - `test_cap_secondary_reposter`: artist X is secondary on 7 tracks (each track has another primary). Cap=5 → only 5 surface, regardless of primary.
   - `test_cap_preserves_order`: input ranked; output preserves input order.

3. **`TestRunDiscoverySyncDBOnly`** — `web/backend/discovery_sync.py::run_discovery_sync`
   - `test_dry_run_no_writes`: snapshot `playlist_tracks` count for playlist_id 26 before & after `run_discovery_sync(dry_run=True)`. Assert equal.
   - `test_wet_run_pushes_to_local_playlist`: with `dry_run=False` and SC push mocked, local `playlist_tracks` has up to 100 rows, all top-200, none owned.
   - `test_deep_playlist_path`: with deep playlist row configured, second `_push_to_sc_playlist` call fires with deep candidates.
   - `test_mixes_playlist_path`: with mixes playlist row configured, third `_push_to_sc_playlist` call fires with long-duration candidates.
   - `test_errors_logged_to_sync_log`: SC push mocked to fail. After run, `discovery_sync_log.errors` row contains JSON with the error string.

4. **`TestPrepareForSyncPartialRefillRewrite`** — `web/backend/discovery_sync.py::prepare_for_sync`
   - `test_no_session_full_replace_wet`: returns `(100, [])`, `playlist_tracks` deleted, `track_count` zeroed.
   - `test_no_session_dry_run`: returns `(100, [])`, `playlist_tracks` unchanged.
   - `test_active_session_partial_wet`: active session with 1 bucket assignment + 99 unassigned. After call: 1 marked liked, returns `(1, [99 sc_ids])`, target_count=1, `recalculate_artist_stats` invoked (mock or assert via stats column delta).
   - `test_active_session_dry_run`: same setup, `dry_run=True`. No mark, no DELETE, no stats call. Return shape still `(1, [99 sc_ids])`.

**Migrate / delete existing tests:**

| Existing test | Action |
|---|---|
| `TestUnplacedBackfillTopOnly` (uses removed `get_unplaced_short_tracks`) | DELETE — coverage moved to `TestGetRepostCandidates::test_status_excludes_liked_dismissed` |
| `TestSeenIdsScope` | DELETE — coverage in `TestGetRepostCandidates::test_status_excludes_liked_dismissed` |
| `TestBackfillNullReposted` | DELETE — coverage in `TestGetRepostCandidates::test_null_reposted_excluded` |
| `TestBackfillExcludesOwned` | DELETE — coverage in `test_owned_exclusion_*` |
| `TestReposterWriteTimestamp` | DELETE — sync no longer writes; feed worker test covers |
| `TestFreshPathExcludesOwned` | DELETE — coverage in `TestRunDiscoverySyncDBOnly::test_wet_run_pushes_to_local_playlist` |

**Test fixtures:** reuse existing `seed_*` helpers in `tests/test_feed_sync.py`. SC push must be mocked (no live API). DB uses isolated tmpdir SQLite (existing fixture pattern). Test fixture must call `_ensure_sync_log_columns(conn)` after the table is created, since the lazy migration runs on first `log_sync_run` (matches prod path).

## Verification

```bash
# All tests pass
rtk uv run pytest tests/test_feed_sync.py -q

# Specific new classes
rtk uv run pytest tests/test_feed_sync.py::TestGetRepostCandidates -v
rtk uv run pytest tests/test_feed_sync.py::TestApplyPerArtistCap -v
rtk uv run pytest tests/test_feed_sync.py::TestRunDiscoverySyncDBOnly -v
rtk uv run pytest tests/test_feed_sync.py::TestPrepareForSyncPartialRefillRewrite -v

# Coverage roughly preserved
rtk uv run pytest tests/test_feed_sync.py --cov=web.backend.discovery_sync --cov=web.backend.queries.discovery --cov-report=term-missing -q

# Lint
rtk uv run ruff check tests/test_feed_sync.py
```

Expect: all green, coverage ≥ pre-change for the two modules.
