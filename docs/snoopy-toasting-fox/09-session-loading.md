---
task: 09-session-loading
status: deferred
depends: [03-backend-api]
deferred_reason: Inverse sync deferred to separate follow-up plan
files:
  - path: web/backend/queries/buckets.py
    action: modify
---

# Session Loading: Compute Bucket Contents from Linked Playlists

**DEFERRED TO SEPARATE PLAN** - This task implements inverse sync (external playlist changes reflected in buckets). Forward sync (assign to bucket → add to playlist) ships first without this complexity.

## Original Context
When the organizer session loads, buckets linked to playlists should show tracks that exist in BOTH the linked playlist AND the parent playlist being organized. This is the inverse sync feature - external playlist changes reflected in buckets.

## Files to Modify/Create
- web/backend/queries/buckets.py (modify - specifically `get_session_with_data` or equivalent)

## Implementation Details

### Modify session loading query to compute linked bucket contents:

```python
def get_session_with_data(session_id: str) -> dict | None:
    """Get session with buckets, track assignments, and linked playlist data."""
    with get_db_connection() as conn:
        # Get session
        session = conn.execute(
            "SELECT * FROM bucket_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        if not session:
            return None

        parent_playlist_id = session["playlist_id"]

        # Get buckets with link info
        buckets = conn.execute("""
            SELECT b.*, bpl.playlist_id as linked_playlist_id, p.name as linked_playlist_name
            FROM buckets b
            LEFT JOIN bucket_playlist_links bpl ON b.id = bpl.bucket_id
            LEFT JOIN playlists p ON bpl.playlist_id = p.id
            WHERE b.session_id = ?
            ORDER BY b.position
        """, (session_id,)).fetchall()

        # For each bucket, compute track_ids
        bucket_data = []
        all_assigned_track_ids = set()

        for bucket in buckets:
            # Get manually assigned tracks
            manual_tracks = conn.execute("""
                SELECT track_id FROM bucket_tracks WHERE bucket_id = ?
                ORDER BY position
            """, (bucket["id"],)).fetchall()
            manual_track_ids = [r["track_id"] for r in manual_tracks]

            # If linked, compute intersection tracks
            linked_track_ids = []
            if bucket["linked_playlist_id"]:
                # Tracks in linked playlist that are ALSO in parent playlist
                linked_tracks = conn.execute("""
                    SELECT lpt.track_id
                    FROM playlist_tracks lpt
                    INNER JOIN playlist_tracks ppt ON lpt.track_id = ppt.track_id
                    WHERE lpt.playlist_id = ?
                    AND ppt.playlist_id = ?
                """, (bucket["linked_playlist_id"], parent_playlist_id)).fetchall()
                linked_track_ids = [r["track_id"] for r in linked_tracks]

            # Merge: manual + linked (dedup, preserve manual order)
            seen = set(manual_track_ids)
            combined_track_ids = manual_track_ids.copy()
            for tid in linked_track_ids:
                if tid not in seen:
                    combined_track_ids.append(tid)
                    seen.add(tid)

            all_assigned_track_ids.update(combined_track_ids)

            bucket_data.append({
                "id": bucket["id"],
                "name": bucket["name"],
                "emoji_id": bucket["emoji_id"],
                "position": bucket["position"],
                "track_ids": combined_track_ids,
                "linked_playlist_id": bucket["linked_playlist_id"],
                "linked_playlist_name": bucket["linked_playlist_name"],
            })

        # Get all tracks in parent playlist
        all_playlist_tracks = conn.execute("""
            SELECT track_id FROM playlist_tracks WHERE playlist_id = ?
        """, (parent_playlist_id,)).fetchall()
        all_playlist_track_ids = {r["track_id"] for r in all_playlist_tracks}

        # Unassigned = in parent playlist but not in any bucket
        unassigned = [tid for tid in all_playlist_track_ids if tid not in all_assigned_track_ids]

        return {
            "id": session["id"],
            "playlist_id": parent_playlist_id,
            "status": session["status"],
            "buckets": bucket_data,
            "unassigned_track_ids": unassigned,
        }
```

### Key logic:
1. For each bucket with a linked playlist, get tracks that are in BOTH linked playlist AND parent playlist
2. Merge with manually assigned tracks (dedup, manual assignments take priority for ordering)
3. Track appears in bucket if: manually assigned OR (in linked playlist AND in parent playlist)

## Verification

1. Create playlist "Dubstep" with tracks A, B, C
2. Create playlist "EDM" with tracks A, B, D, E
3. Open organizer for "EDM", create bucket "dubstep", link to "Dubstep" playlist
4. Bucket should show tracks A, B (intersection of Dubstep and EDM)
5. Track C (in Dubstep but not EDM) should NOT appear in bucket
6. Track D, E (in EDM but not Dubstep) should be unassigned
