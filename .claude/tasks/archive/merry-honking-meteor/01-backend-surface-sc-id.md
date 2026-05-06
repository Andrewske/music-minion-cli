---
task: 01-backend-surface-sc-id
status: pending
depends: []
files:
  - path: web/backend/queries/buckets.py
    action: modify
---

# Surface soundcloud_playlist_id to Frontend

## Context
The frontend needs to know whether a bucket's linked playlist has a SoundCloud connection, so it can conditionally show the sync button. The query already joins the `playlists` table — we just need one more column.

## Files to Modify
- `web/backend/queries/buckets.py` (modify)

## Implementation Details

In `get_session_with_data()` (line ~121), update the SELECT to add:
```sql
p.soundcloud_playlist_id as linked_playlist_soundcloud_id
```

In the bucket dict construction (line ~148), add:
```python
"linked_playlist_soundcloud_id": bucket_row["linked_playlist_soundcloud_id"],
```

## Verification
- Start the backend and hit `POST /api/buckets/sessions` with a playlist that has buckets linked to SC playlists
- Verify the response includes `linked_playlist_soundcloud_id` on each bucket
