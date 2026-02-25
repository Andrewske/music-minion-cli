---
task: 04-extend-keyboard-shortcuts
status: done
depends: [03-update-parent-drag-handler]
files:
  - path: web/frontend/src/pages/PlaylistOrganizer.tsx
    action: modify
---

# Extend Keyboard Shortcuts for Bucket-to-Bucket Moves

## Context

Extend the existing Shift+1-9 keyboard shortcuts to support moving tracks between buckets, not just unassigned→bucket. When the currently playing track is already in a bucket, pressing Shift+number should move it to the target bucket.

## Files to Modify

- `web/frontend/src/pages/PlaylistOrganizer.tsx` (modify)

## Implementation Details

### Change: Update handleAssignCurrentTrack Function

**Location**: Lines 85-93 (handleAssignCurrentTrack callback)

Replace the current implementation with:

```typescript
const handleAssignCurrentTrack = useCallback(
  async (bucketId: string): Promise<void> => {
    if (!currentTrack) return;

    // Find which bucket (if any) currently contains this track
    const currentBucket = buckets.find((b) => b.track_ids.includes(currentTrack.id));

    // If already in target bucket, no-op
    if (currentBucket?.id === bucketId) return;

    await assignTrack(bucketId, currentTrack.id);

    // Only auto-advance if moving from unassigned
    if (!currentBucket) {
      playNextUnassignedTrack(currentTrack.id);
    }
  },
  [currentTrack, buckets, assignTrack, playNextUnassignedTrack]
);
```

### Design Decisions Explained

**Check current bucket**: The `buckets.find()` call determines if the track is currently in a bucket or unassigned.

**Same-bucket no-op**: If user presses Shift+3 while track is already in Bucket 3, nothing happens (silent no-op, consistent with drag-and-drop behavior).

**Auto-advance only from unassigned**: When moving from unassigned→bucket, auto-advance plays the next unassigned track. When moving bucket→bucket, no auto-advance (user is organizing, not listening).

**assignTrack handles removal**: The `assignTrack` API automatically removes the track from its old bucket, so no explicit unassign call is needed.

## Verification

1. Build TypeScript: `npx tsc --noEmit`
   - Should compile with no errors

2. Start web mode: `music-minion --web`
   - Navigate to playlist organizer
   - Create at least 3 buckets with tracks

3. **Test Unassigned → Bucket (Verify No Regression)**:
   - Play an unassigned track
   - Press Shift+1
   - **Expected**: Track assigns to Bucket 1, next unassigned track plays

4. **Test Bucket → Different Bucket (New Feature)**:
   - Play a track in Bucket 1
   - Press Shift+2
   - **Expected**:
     - Track moves from Bucket 1 to Bucket 2
     - Playback continues (no auto-advance)
     - No toast notification (silent success, consistent with drag-and-drop)

5. **Test Bucket → Same Bucket (No-op)**:
   - Play a track in Bucket 2
   - Press Shift+2
   - **Expected**: Nothing happens (silent no-op)

6. **Test While Not Playing**:
   - Stop playback (no current track)
   - Press Shift+1
   - **Expected**: Nothing happens (no current track to assign)

7. **Test Rapid Keypresses**:
   - Play a track in Bucket 1
   - Rapidly press Shift+2, Shift+3, Shift+1
   - **Expected**: Track moves through buckets, no race conditions
