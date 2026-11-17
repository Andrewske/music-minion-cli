# Bucket "Apply rating": bulk ELO from manual bucket order

Status: draft, 2026-11-16. Branch: `feat/organizer-bucket-track-rows` (adds drag-to-reorder rows inside a bucket).

## Goal

In the Playlist Organizer, the user drags tracks inside a bucket into preference order (top = best). One click on "Apply rating" turns that order into playlist ELO ratings, replacing hundreds of 1v1 comparisons.

## Decisions already made

- **Target playlist** is `bucket_sessions.playlist_id` (the playlist being organized). Never the bucket's linked playlist.
- **No synthetic comparisons.** Nothing goes into `playlist_comparison_history`. `get_next_playlist_pair` treats any pair in history as done globally, and `get_contextual_track_stats` counts history W/L, so fake rows would poison both.
- **Redistribute, don't invent.** The bucket's current ratings are re-dealt in the new order. Buckets are usually themes (vocal, dark, peak-time), so stretching each to the playlist's full range would falsely equate the #1 of every theme. Redistribution keeps each bucket's existing spread and level. When a bucket is an occasional quality tier, its ratings are already high or low, so it works without a tier mode.
- **Counters untouched.** `comparison_count`, `wins`, `losses`, `last_compared` stay as they are. Ratings with no row get a new row with zeros. (The web router uses fixed K=32, so faking counts buys nothing.)
- **One application record** per click, with before/after snapshots, for undo and for later "ranked above N" displays.
- **Out of scope for v1:** playlist re-sort, file-comment ELO export, a tier toggle, Bradley-Terry refit, "ranked above N tracks" UI. All stay separate, explicit steps or follow-ups.

## Algorithm

Pure function in a new `src/music_minion/domain/rating/bulk.py`:

```python
FALLBACK_HALF_WIDTH = 100.0  # unrated bucket -> 1600 .. 1400
MIN_SPREAD = 1.0             # pool spread below this counts as "unrated"

def compute_rank_ratings(
    ordered_track_ids: list[int], current: dict[int, float]
) -> tuple[dict[int, float], str]:
    """Return ({track_id: new_rating}, method) for a best-first order.

    method = 'redistribute' | 'band'
    """
```

1. `pool = [current.get(tid, 1500.0) for tid in ordered_track_ids]`.
2. If `max(pool) - min(pool) >= MIN_SPREAD`: sort pool descending and zip with the order. Method `redistribute`.
3. Otherwise (all 1500, or all equal): linear band centred on the pool's value, `center + H` for #1 down to `center - H` for last. Method `band`.
4. n < 2: reject (caller returns 400).

Known accepted trade-off: in a mixed bucket, unrated tracks bring 1500s into the pool and pull established tracks toward the middle. Fine for v1.

## Data model (schema v78)

```sql
CREATE TABLE bucket_rank_applications (
    id TEXT PRIMARY KEY,                 -- uuid
    bucket_id TEXT REFERENCES buckets(id) ON DELETE SET NULL,
    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    method TEXT NOT NULL,                -- 'redistribute' | 'band'
    snapshot TEXT NOT NULL,              -- JSON: [{track_id, before, after, had_row, comparison_count}] in rank order
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    undone_at TIMESTAMP
);
CREATE INDEX idx_bucket_rank_apps_bucket ON bucket_rank_applications(bucket_id, created_at DESC);
```

Migration via `_migrate_v78_bucket_rank_applications(conn)` with the existing SAVEPOINT pattern in `core/database.py`. Bump `SCHEMA_VERSION`.

`snapshot` order doubles as the stored ranking, so a later "ranked above N" display derives from it with no extra table.

## Backend

### Queries (`web/backend/queries/bucket_rank.py`)

- `get_bucket_rank_context(conn, bucket_id) -> (playlist_id, ordered_track_ids) | None`: reuses `_visible_bucket_track_ids` so hidden memberships (tracks removed from the playlist) are skipped. Order comes from the DB, not the client, so the server always rates what it stored.
- `preview_bucket_rating(bucket_id) -> dict`: reads current ratings (`playlist_elo_ratings` for the playlist), runs `compute_rank_ratings`, returns rows `{track_id, before, after}`, `method`, and the band endpoints when `method == 'band'`. No writes.
- `apply_bucket_rating(bucket_id, expected_track_ids) -> dict`: one connection, `BEGIN IMMEDIATE` **before any read** (`get_db_connection()` does not open a transaction itself; follow `queries/buckets.py:85`). Then:
  - re-read the visible order; if it differs from `expected_track_ids` (the order the preview showed), roll back and return 409 so the dialog refreshes;
  - compute, insert the application row;
  - `executemany` upsert: `INSERT INTO playlist_elo_ratings (track_id, playlist_id, rating) VALUES (?,?,?) ON CONFLICT(track_id, playlist_id) DO UPDATE SET rating = excluded.rating, updated_at = CURRENT_TIMESTAMP` (composite PK supports this);
  - one commit. Returns the application id plus rows.
- `undo_bucket_rating(application_id) -> dict`, also under `BEGIN IMMEDIATE`:
  - **Stack rule:** only the newest non-undone application for that playlist can be undone; anything older is a 409. This stops undoing A from clobbering a later B that touched the same tracks (same bucket re-applied, or a track in two buckets).
  - For each snapshot entry, restore only if the current rating still equals `after` (within 1e-6) **and** `comparison_count` equals the snapshot's; otherwise skip it (a real comparison happened since).
  - Entries with `had_row = false` that pass the check get their row deleted, so only rows this feature created are removed.
  - Sets `undone_at`. Returns `{restored, skipped}`. Undoing twice is a 409.

Accepted race: the comparison router reads ratings on separate connections before writing (`routers/comparisons.py:146`), so a comparison recorded during an apply could write a stale value. Single user, never in practice; not worth locking.

### Routes (`web/backend/routers/buckets.py`)

- `GET  /api/buckets/{bucket_id}/rating/preview` -> `{method, rows: [{track_id, before, after}]}`
- `POST /api/buckets/{bucket_id}/rating/apply` body `{track_ids}` -> `{application_id, method, rows}`
- `POST /api/buckets/rating-applications/{application_id}/undo` -> `{restored, skipped}`

Errors follow the router's existing pattern: 404 unknown bucket or application, 400 fewer than 2 visible tracks, 409 stale order / not newest / already undone, `logger.exception` + 500 otherwise. Existing `/{bucket_id}` params match a single segment, so the undo path is not shadowed.

## Frontend

- `web/frontend/src/api/buckets.ts`: `previewBucketRating`, `applyBucketRating`, `undoBucketRating`.
- `Bucket.tsx`: add "Apply rating" in **both** places Shuffle lives: the desktop header buttons (`Bucket.tsx:237`) and the mobile dropdown (`Bucket.tsx:291`). Disabled when `tracks.length < 2` or a reorder mutation for this bucket is pending.
- New `ApplyRatingDialog.tsx`: fetches the preview on open, shows rank, title, `before → after`, delta (green/red), and the method ("Re-dealt this bucket's ratings" or "Unrated bucket: spread {high} to {low}" using the real endpoints from the preview). Confirm sends the previewed `track_ids`; on 409 it refetches the preview.
- On success: toast with an Undo action holding the application id (calls undo, reports skipped count if any; on 409 says a newer apply exists).
- After apply **and** undo, invalidate `['playlist', playlistId, 'tracks', 'all']` (the organizer's cache, `PlaylistOrganizer.tsx:94`) and `['playlist-tracks', playlistId]`. Ratings come from `routers/playlists.py` via `COALESCE(per.rating, 1500)`.
- Expose the reorder mutation's pending state from `usePlaylistOrganizer.ts` (`:290`); the apply/undo mutations live next to the shuffle mutation.

## Tests

- `compute_rank_ratings`: redistribute keeps the multiset of ratings; an already-correct order is a no-op under redistribute; all-1500 uses the band; equal non-1500 pool uses a band around that value; n<2 raises.
- Queries (pytest, temp DB like `test_bucket_sessions.py`): apply writes ratings and one application row, leaves counters and history untouched; tracks hidden from the playlist are skipped; stale `expected_track_ids` is a 409 with no writes; undo restores; undo skips a track whose rating or comparison_count changed; undo deletes only created rows; second undo is 409; apply A then B (same bucket, and overlapping buckets), undo A is 409, undo B then A works.
- Router: 404 / 400 paths.
- Frontend: dialog renders the preview and calls apply (vitest, alongside `Bucket.test.tsx`).

## Resolved questions (after GPT review)

1. Pending drag state: button waits for the reorder mutation; the `track_ids` check catches anything else. No warning UI.
2. Auto-apply on drag: no, explicit button only.
3. Fallback ±100: keep. A 200-point gap means about 76% expected win rate for #1 over last under `elo.py`, a meaningful start that real comparisons can still move.
