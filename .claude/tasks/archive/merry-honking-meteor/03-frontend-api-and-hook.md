---
task: 03-frontend-api-and-hook
status: pending
depends: [02-backend-sync-logic]
files:
  - path: web/frontend/src/api/buckets.ts
    action: modify
  - path: web/frontend/src/hooks/usePlaylistOrganizer.ts
    action: modify
---

# Frontend API Types and Hook Mutation

## Context
Add the TypeScript types, API function, and React Query mutation so the frontend can call the sync endpoint.

## Files to Modify
- `web/frontend/src/api/buckets.ts` (modify)
- `web/frontend/src/hooks/usePlaylistOrganizer.ts` (modify)

## Implementation Details

### API types and function (`buckets.ts`)

Add to `Bucket` interface:
```typescript
linked_playlist_soundcloud_id: string | null;
```

Add response type and function:
```typescript
export interface SyncSoundCloudResponse {
  pulled: number;
  pushed_adds: number;
  pushed_removals: number;
  skipped: number;
  errors: string[];
}

export async function syncBucketSoundCloud(bucketId: string): Promise<SyncSoundCloudResponse> {
  const response = await fetch(`${API_BASE}/buckets/${bucketId}/sync-soundcloud`, {
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
- `syncBucketSoundCloud: (bucketId: string) => Promise<SyncSoundCloudResponse>`
- `syncingBucketId: string | null` — tracks which bucket is currently syncing (from `syncSoundCloudMutation.isPending ? syncSoundCloudMutation.variables : null`). This scopes the loading state per-bucket instead of globally.

## Verification
- TypeScript compiles without errors
- Hook returns the new properties
