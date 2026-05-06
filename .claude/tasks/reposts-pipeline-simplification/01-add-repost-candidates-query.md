---
task: 01-add-repost-candidates-query
status: pending
depends: []
files:
  - path: web/backend/queries/discovery.py
    action: modify
---

# Add `get_repost_candidates` SQL Query + Per-Artist Cap Helper

## Context

Single-SQL replacement for the multi-step repost selection pipeline. Picks ranked candidates from `discovery_track_reposters`/`discovery_tracks`/`discovery_artists` with owned/duration/window filters. Returns the per-track aggregated reposter artist IDs so a small Python helper can apply the per-artist cap (≤5) deterministically across **all** reposters, not just the highest-ranked one. No SC API call. Foundation for Step 4 (slim `run_discovery_sync`) and Step 6 (tests).

## Files to Modify/Create

- `web/backend/queries/discovery.py` (modify) — add `get_repost_candidates` and `apply_per_artist_cap`

## Implementation Details

Add `get_repost_candidates` to `web/backend/queries/discovery.py`:

```python
def get_repost_candidates(
    exclude_playlist_id: int,
    exclude_sc_ids: set[str],
    window_days_min: int = 0,
    window_days_max: int = 365_000,
    duration_min_ms: int = 120_000,
    duration_max_ms: int = 600_000,
    limit: int = 300,
) -> list[dict[str, Any]]:
    """Pick a ranked pool of repost candidates.

    Score order:
      1. reposter_count DESC  — multi-reposter consensus
      2. avg_hit_rate DESC    — artist quality
      3. latest_repost DESC   — recency

    Returns up to `limit` rows. Caller applies per-artist cap via
    `apply_per_artist_cap`, then truncates to the playlist target.
    Default `limit=300` gives ~3x headroom for capping.

    Args:
      exclude_playlist_id: the discovery playlist id (kept tracks pass through).
      exclude_sc_ids: SC IDs already kept this run (partial-refill case).
      window_days_min/max: filter on reposted_at age (in days from now).
      duration_min_ms/max_ms: track duration window. Defaults to short tracks
        (2–10 min). Pass `duration_min_ms=600_000, duration_max_ms=7_200_000`
        for mixes.
      limit: max rows returned from SQL (pre-cap).
    """
    sc_ids_placeholder = ",".join("?" * len(exclude_sc_ids)) or "''"
    args = [
        exclude_playlist_id,
        window_days_min,
        window_days_max,
        duration_min_ms,
        duration_max_ms,
        *exclude_sc_ids,
        limit,
    ]
    sql = f"""
    WITH owned AS (
      SELECT t.soundcloud_id FROM tracks t
      WHERE t.soundcloud_id IS NOT NULL
        AND (
          t.id IN (SELECT track_id FROM playlist_tracks WHERE playlist_id != ?)
          OR t.id IN (SELECT track_id FROM ratings WHERE rating_type = 'love')
        )
    ),
    candidates AS (
      SELECT
        dt.id AS discovery_track_id,
        dt.soundcloud_id,
        dt.title,
        dt.artist_name,
        dt.duration_ms,
        MAX(dtr.reposted_at) AS latest_repost,
        COUNT(*) AS reposter_count,
        AVG(da.hit_rate) AS avg_hit_rate,
        json_group_array(da.id) AS reposter_artist_ids
      FROM discovery_track_reposters dtr
      JOIN discovery_tracks dt ON dt.id = dtr.discovery_track_id
      JOIN discovery_artists da ON da.id = dtr.discovery_artist_id AND da.in_top_200 = 1
      WHERE dt.status NOT IN ('liked', 'dismissed')
        AND dtr.reposted_at IS NOT NULL
        AND julianday('now') - julianday(dtr.reposted_at) BETWEEN ? AND ?
        AND dt.duration_ms BETWEEN ? AND ?
        AND dt.soundcloud_id NOT IN ({sc_ids_placeholder})
        AND dt.soundcloud_id NOT IN (SELECT soundcloud_id FROM owned)
      GROUP BY dt.id
    )
    SELECT soundcloud_id, title, artist_name, duration_ms,
           latest_repost, reposter_count, avg_hit_rate, reposter_artist_ids
    FROM candidates
    ORDER BY reposter_count DESC, avg_hit_rate DESC, latest_repost DESC
    LIMIT ?
    """
    with get_db_connection() as conn:
        rows = conn.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


def apply_per_artist_cap(
    candidates: list[dict[str, Any]],
    target: int,
    cap: int = 5,
) -> list[dict[str, Any]]:
    """Greedy per-artist cap: walk candidates in rank order, drop a track
    if any of its reposters has already filled `cap` slots in the result.

    Args:
      candidates: rows from `get_repost_candidates` (already ranked).
      target: max rows to return.
      cap: per-artist limit (default 5).
    """
    counts: dict[int, int] = {}
    out: list[dict[str, Any]] = []
    for row in candidates:
        artist_ids = json.loads(row["reposter_artist_ids"])
        if any(counts.get(aid, 0) >= cap for aid in artist_ids):
            continue
        for aid in artist_ids:
            counts[aid] = counts.get(aid, 0) + 1
        out.append(row)
        if len(out) >= target:
            break
    return out
```

Notes:
- Argument order in `args` matches the order `?` placeholders appear in SQL: `playlist_id` (CTE) → `window_min/max` (BETWEEN) → `duration_min/max` (BETWEEN) → `*sc_ids` (NOT IN) → `limit`.
- `sc_ids_placeholder` always falsy-safe (`"''"` when empty set; `args` only spreads ids when non-empty).
- `reposter_artist_ids` returned as JSON text (sqlite `json_group_array`); helper parses with `json.loads`.
- Per-artist cap done in Python, applies to **every** reposter on a track (not just primary). Survives `discovery_artists.ranking` ties.
- `import json` at top of file if not already present.

## Verification

```bash
# Function imports cleanly
uv run python -c "from web.backend.queries.discovery import get_repost_candidates, apply_per_artist_cap; print(get_repost_candidates.__doc__[:60])"

# Smoke test against live DB (read-only)
uv run python -c "
from web.backend.queries.discovery import get_repost_candidates, apply_per_artist_cap
pool = get_repost_candidates(exclude_playlist_id=26, exclude_sc_ids=set(), limit=300)
capped = apply_per_artist_cap(pool, target=100)
print(f'pool={len(pool)} capped={len(capped)}')
for r in capped[:3]:
    print(r['title'][:40], r['reposter_count'], r['avg_hit_rate'])
"

# Mixes path smoke
uv run python -c "
from web.backend.queries.discovery import get_repost_candidates, apply_per_artist_cap
pool = get_repost_candidates(
    exclude_playlist_id=26, exclude_sc_ids=set(),
    duration_min_ms=600_000, duration_max_ms=7_200_000, limit=60,
)
print('mixes pool:', len(pool))
"

# Lint
rtk uv run ruff check web/backend/queries/discovery.py
```

Expect: pool ≤ 300, capped ≤ 100, descending `reposter_count`, ruff clean.
