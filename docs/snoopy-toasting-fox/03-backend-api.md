---
task: 03-backend-api
status: done
depends: [02-backend-queries]
files:
  - path: web/backend/routers/buckets.py
    action: modify
  - path: web/backend/schemas.py
    action: modify
---

# Backend API: Link Endpoints and Response Models

## Context
Exposes linking functionality via REST API and updates bucket responses to include link information. Also modifies session loading to compute bucket contents from linked playlists.

## Files to Modify/Create
- web/backend/routers/buckets.py (modify)
- web/backend/schemas.py (modify - if response models live here)

## Implementation Details

### New Pydantic models:

```python
class LinkBucketBody(BaseModel):
    playlist_id: int | None  # None to unlink
```

### Update BucketResponse:

```python
class BucketResponse(BaseModel):
    id: str
    name: str
    emoji_id: str | None
    position: int
    track_ids: list[int]
    linked_playlist_id: int | None  # NEW
    linked_playlist_name: str | None  # NEW
```

### New API endpoints:

```python
@router.post("/{bucket_id}/link")
async def link_bucket_endpoint(bucket_id: str, body: LinkBucketBody):
    """Link/unlink bucket to playlist."""
    if body.playlist_id is None:
        success = bucket_queries.unlink_bucket(bucket_id)
    else:
        success = bucket_queries.link_bucket_to_playlist(bucket_id, body.playlist_id)
    if not success:
        raise HTTPException(status_code=404, detail="Bucket not found")
    return {"linked": body.playlist_id is not None}

@router.get("/{bucket_id}/link")
async def get_bucket_link_endpoint(bucket_id: str) -> dict:
    """Get current link status for bucket."""
    playlist_id = bucket_queries.get_bucket_link(bucket_id)
    return {"playlist_id": playlist_id}
```

**Note:** Session loading changes are detailed in task 09 (09-session-loading.md).

## Verification

1. Start backend: `uv run uvicorn web.backend.main:app --reload`
2. Test link endpoint:
   ```bash
   curl -X POST http://localhost:8642/api/buckets/{bucket_id}/link \
     -H "Content-Type: application/json" \
     -d '{"playlist_id": 123}'
   ```
3. Test get link:
   ```bash
   curl http://localhost:8642/api/buckets/{bucket_id}/link
   ```
4. Verify session response includes `linked_playlist_id` and `linked_playlist_name`:
   ```bash
   curl http://localhost:8642/api/buckets/sessions/{session_id}
   ```
