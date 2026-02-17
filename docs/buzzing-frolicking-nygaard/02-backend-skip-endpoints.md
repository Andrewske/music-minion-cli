---
task: 02-backend-skip-endpoints
status: pending
depends: [01-backend-exclusion-filter]
files:
  - path: web/backend/routers/playlists.py
    action: modify
---

# Backend: Add Skip Endpoints for Smart Playlists

## Context
Users need API endpoints to skip/unskip tracks from smart playlists. These endpoints will insert/delete from `playlist_builder_skipped` table, reusing existing domain functions from the manual playlist builder.

## Files to Modify/Create
- web/backend/routers/playlists.py (modify)

## Implementation Details
Add three endpoints to the playlists router:

1. **`POST /playlists/{playlist_id}/skip/{track_id}`** - Skip a track
   - Validate playlist exists and is smart type
   - Call existing `builder.skip_track(playlist_id, track_id)` function
   - Return 200 on success

2. **`DELETE /playlists/{playlist_id}/skip/{track_id}`** - Unskip a track
   - Validate playlist exists and is smart type
   - Call existing `builder.unskip_track(playlist_id, track_id)` function
   - Return 200 on success

3. **`GET /playlists/{playlist_id}/skipped`** - List skipped tracks
   - Validate playlist exists and is smart type
   - Call existing `builder.get_skipped_tracks(playlist_id)` function
   - Return list of skipped tracks with metadata

The domain functions in `src/music_minion/domain/playlists/builder.py` already handle the database operations - just wire them to new endpoints.

## Verification
1. `POST /playlists/{id}/skip/{track_id}` - verify row inserted into `playlist_builder_skipped`
2. `GET /playlists/{id}/skipped` - verify returns the skipped track
3. `DELETE /playlists/{id}/skip/{track_id}` - verify row removed
4. `GET /playlists/{id}/skipped` - verify empty list
