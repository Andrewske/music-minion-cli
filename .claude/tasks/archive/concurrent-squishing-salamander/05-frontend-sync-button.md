---
task: 05-frontend-sync-button
status: done
depends: [03-surface-sc-id, 04-manual-sync-endpoint]
files:
  - path: web/frontend/src/api/buckets.ts
    action: modify
  - path: web/frontend/src/hooks/usePlaylistOrganizer.ts
    action: modify
  - path: web/frontend/src/components/organizer/Bucket.tsx
    action: modify
  - path: web/frontend/src/pages/PlaylistOrganizer.tsx
    action: modify
---

# Frontend Sync Button

## Context
Add a per-bucket SoundCloud sync button (RefreshCw icon) that triggers the bidirectional sync endpoint. Only visible on buckets linked to SC-backed playlists. Shows spinner during sync and toast feedback on completion.

## Files to Modify
- `web/frontend/src/api/buckets.ts` (modify)
- `web/frontend/src/hooks/usePlaylistOrganizer.ts` (modify)
- `web/frontend/src/components/organizer/Bucket.tsx` (modify)
- `web/frontend/src/pages/PlaylistOrganizer.tsx` (modify)

## Implementation Details

### Types + API function (`api/buckets.ts`)

Add response type:
```typescript
export interface SyncSoundCloudResponse {
  pulled: number;
  pushed_adds: number;
  pushed_removals: number;
  skipped: number;
  errors: string[];
}
```

Add API function:
```typescript
export async function syncBucketSoundCloud(bucketId: string): Promise<SyncSoundCloudResponse> {
  const response = await fetch(`${API_BASE}/${bucketId}/sync-soundcloud`, {
    method: 'POST',
  });
  if (!response.ok) {
    const errorText = await response.text();
    try {
      const error = JSON.parse(errorText);
      throw new Error(error.detail || 'Sync failed');
    } catch {
      throw new Error(errorText || 'Sync failed');
    }
  }
  return response.json();
}
```

### Hook mutation (`usePlaylistOrganizer.ts`)

Add mutation:
```typescript
const syncSoundCloudMutation = useMutation({
  mutationFn: (bucketId: string) => bucketsApi.syncBucketSoundCloud(bucketId),
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey });
    queryClient.invalidateQueries({ queryKey: ['playlists'] });
  },
});
```

Expose from hook return:
- `syncBucketSoundCloud: (bucketId: string) => Promise<SyncSoundCloudResponse>` — wraps `syncSoundCloudMutation.mutateAsync`
- `syncingBucketId: string | null` — `syncSoundCloudMutation.isPending ? syncSoundCloudMutation.variables : null` (scopes loading state per-bucket)

### Bucket header button (`Bucket.tsx`)

Add imports: `RefreshCw, Loader2` from `lucide-react`

Add to `BucketComponentProps`:
```typescript
onSyncSoundCloud?: () => Promise<void>;
isSyncingSoundCloud?: boolean;
```

Add button between Shuffle and Edit in bucket header:
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

### Wiring (`PlaylistOrganizer.tsx`)

Add handler:
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

Pass to BucketComponent:
```tsx
onSyncSoundCloud={() => handleSyncSoundCloud(bucket.id)}
isSyncingSoundCloud={syncingBucketId === bucket.id}
```

## Verification
1. Link a bucket to a SoundCloud playlist → verify RefreshCw icon appears on that bucket only
2. Buckets without SC link → verify no sync button
3. Click sync → verify spinner shows during operation
4. Verify toast success message with pull/push counts
5. Verify toast error on failure (e.g., disconnect network)
6. Add a track on SoundCloud directly → click sync → verify it's pulled into local playlist
7. TypeScript compiles without errors
