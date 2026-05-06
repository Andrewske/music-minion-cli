---
task: 05-delete-dead-code
status: pending
depends: [04-rewrite-run-discovery-sync]
files:
  - path: web/backend/discovery_sync.py
    action: modify
  - path: web/backend/queries/discovery.py
    action: modify
  - path: web/backend/routers/discovery.py
    action: modify
---

# Delete Superseded Pipeline Code (~400+ lines)

## Context

Step 4 above the only caller of these helpers; once `run_discovery_sync` no longer references them, they're dead. Personal project rule: delete unused code immediately. `_fetch_all_reposts` kept (still used by feed worker `sync_followings_reposts`). With mixes now folded into `get_repost_candidates` (Step 4), `_split_by_duration` and `_select_tracks_chronological` also delete cleanly.

## Files to Modify/Create

- `web/backend/discovery_sync.py` (modify) — delete: `_select_tracks_chronological`, `_split_by_duration`, `enrich_repost_timestamps`. Keep `_fetch_all_reposts`.
- `web/backend/queries/discovery.py` (modify) — delete: `get_seen_track_ids`, `get_unplaced_short_tracks`, `compute_slot_caps`, `mark_tracks_in_playlist`, `get_owned_sc_ids` (verify dead first).
- `web/backend/routers/discovery.py` (modify) — delete `enrich_timestamps_endpoint` + its route registration.

## Implementation Details

Deletion table:

| File | Symbol | Action | Notes |
|---|---|---|---|
| `discovery_sync.py` | `_fetch_all_reposts` | KEEP | feed worker `sync_followings_reposts` still uses it |
| `discovery_sync.py` | `_select_tracks_chronological` | DELETE | SQL ORDER BY does selection |
| `discovery_sync.py` | `_split_by_duration` | DELETE | duration filter now in `get_repost_candidates` |
| `discovery_sync.py` | `enrich_repost_timestamps` | DELETE | #4, 15/9984 match rate |
| `queries/discovery.py` | `get_seen_track_ids` | DELETE | inlined in SQL |
| `queries/discovery.py` | `get_unplaced_short_tracks` | DELETE | replaced by `get_repost_candidates` |
| `queries/discovery.py` | `compute_slot_caps` | DELETE | `apply_per_artist_cap` does cap |
| `queries/discovery.py` | `mark_tracks_in_playlist` | DELETE | #13, `playlist_tracks` is authoritative |
| `queries/discovery.py` | `get_owned_sc_ids` | DELETE if no callers | ownership inlined in `get_repost_candidates` SQL — grep first |
| `routers/discovery.py` | `enrich_timestamps_endpoint` (`POST /api/discovery/enrich-timestamps`) | DELETE | #4 |

Process:
1. For each symbol, grep for call sites first. If any non-test caller remains, stop and report — plan invariant violated.
2. Delete the symbol + any now-unused imports.
3. Delete the route decorator + handler in `routers/discovery.py`. Remove from any router includes.

```bash
# Pre-delete grep (run before each delete)
rtk grep -rn "_select_tracks_chronological\|_split_by_duration\|enrich_repost_timestamps\|get_seen_track_ids\|get_unplaced_short_tracks\|compute_slot_caps\|mark_tracks_in_playlist\|get_owned_sc_ids\|enrich_timestamps_endpoint" web/backend/ src/ tests/
```

If only test files match, those tests will be migrated/deleted in Step 6 (tests). Acceptable to have transient red tests between Step 5 and Step 6 commits.

Re-check `_fetch_all_reposts` callers — only `sync_followings_reposts` should reference it after the rewrite.

## Verification

```bash
# No non-test callers remain
rtk grep -rn "_select_tracks_chronological\|_split_by_duration\|enrich_repost_timestamps\|get_seen_track_ids\|get_unplaced_short_tracks\|compute_slot_caps\|mark_tracks_in_playlist\|get_owned_sc_ids\|enrich_timestamps_endpoint" web/backend/ src/

# Frontend doesn't call the deleted endpoint
rtk grep -rn "enrich-timestamps" web/frontend/ shared/ mobile/

# Backend imports still resolve
uv run python -c "from web.backend import discovery_sync; from web.backend.queries import discovery; from web.backend.routers import discovery as r; print('imports OK')"

# Lint
rtk uv run ruff check web/backend/
```

Expect: zero matches in non-test code, zero matches for the endpoint anywhere on the frontend, imports resolve, ruff clean.
