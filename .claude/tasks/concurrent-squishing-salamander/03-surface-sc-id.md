---
task: 03-surface-sc-id
status: done
depends: []
files:
  - path: web/backend/queries/buckets.py
    action: modify
  - path: web/backend/routers/buckets.py
    action: modify
  - path: web/frontend/src/api/buckets.ts
    action: modify
---

# Surface soundcloud_playlist_id in Bucket Response

## Context
The frontend needs to know whether a bucket's linked playlist has a SoundCloud connection, so it can conditionally show the sync button. The query already joins the `playlists` table via `bucket_playlist_links` — we just need one more column propagated through the stack.

## Files to Modify
- `web/backend/queries/buckets.py` (modify)
- `web/backend/routers/buckets.py` (modify)
- `web/frontend/src/api/buckets.ts` (modify)

## Implementation Details

### Backend query (`queries/buckets.py`)

In `get_session_with_data()` (~line 121), update the SELECT to add:
```sql
p.soundcloud_playlist_id as linked_playlist_soundcloud_id
```

The query already has `LEFT JOIN playlists p ON bpl.playlist_id = p.id`, so no new join needed.

In bucket dict construction (~line 148), add:
```python
"linked_playlist_soundcloud_id": bucket_row["linked_playlist_soundcloud_id"],
```

In `create_bucket()` return dict (~line 227), add:
```python
"linked_playlist_soundcloud_id": None,
```

### Backend router (`routers/buckets.py`)

Add to `BucketResponse` Pydantic model (~line 59):
```python
linked_playlist_soundcloud_id: str | None = None
```

### Frontend types (`api/buckets.ts`)

Add to `Bucket` interface (~line 21):
```typescript
linked_playlist_soundcloud_id: string | null;
```

## Verification
- Start backend, hit `POST /api/buckets/sessions` with a playlist that has buckets linked to SC playlists
- Verify response includes `linked_playlist_soundcloud_id` on each bucket
- Buckets not linked to SC playlists should have `null`
- TypeScript compiles without errors
