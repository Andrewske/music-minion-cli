---
task: 04-frontend-sync-button
status: pending
depends: [03-frontend-api-and-hook]
files:
  - path: web/frontend/src/components/organizer/Bucket.tsx
    action: modify
  - path: web/frontend/src/pages/PlaylistOrganizer.tsx
    action: modify
---

# Sync Button UI and Wiring

## Context
Add the sync button to the bucket header (between Shuffle and Edit) and wire it up in the PlaylistOrganizer page with toast feedback.

## Files to Modify
- `web/frontend/src/components/organizer/Bucket.tsx` (modify)
- `web/frontend/src/pages/PlaylistOrganizer.tsx` (modify)

## Implementation Details

### Bucket.tsx

Add to imports: `RefreshCw, Loader2` from `lucide-react`

Add to `BucketComponentProps`:
```typescript
onSyncSoundCloud?: () => Promise<void>;
isSyncingSoundCloud?: boolean;  // scoped per-bucket via syncingBucketId comparison
```

Add button between Shuffle and Edit (after line ~269):
```tsx
{bucket.linked_playlist_soundcloud_id && (
  <button
    type="button"
    onClick={(e) => {
      e.stopPropagation();
      onSyncSoundCloud?.();
    }}
    disabled={isSyncingSoundCloud}
    className="p-1.5 text-white/40 hover:text-orange-400 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
    title="Sync with SoundCloud"
  >
    {isSyncingSoundCloud ? (
      <Loader2 className="w-4 h-4 animate-spin" />
    ) : (
      <RefreshCw className="w-4 h-4" />
    )}
  </button>
)}
```

### PlaylistOrganizer.tsx

Wire up the handler using the hook's `syncBucketSoundCloud`:

```typescript
const handleSyncSoundCloud = async (bucketId: string) => {
  try {
    const result = await syncBucketSoundCloud(bucketId);
    toast.success(`SC sync: ${result.pulled} pulled, ${result.pushed_adds} added, ${result.pushed_removals} removed`);
  } catch (error) {
    toast.error(`SoundCloud sync failed: ${error instanceof Error ? error.message : String(error)}`);
  }
};
```

Pass to `BucketComponent`:
```tsx
onSyncSoundCloud={() => handleSyncSoundCloud(bucket.id)}
isSyncingSoundCloud={syncingBucketId === bucket.id}
```

## Verification
1. Link a bucket to a SoundCloud playlist → verify RefreshCw icon appears on that bucket only
2. Buckets without SC link → verify no sync button
3. Click sync → verify spinner shows during operation
4. Verify toast success message with counts
5. Verify toast error message on failure (e.g., disconnect network)
