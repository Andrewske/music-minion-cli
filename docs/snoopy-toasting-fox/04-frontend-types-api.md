---
task: 04-frontend-types-api
status: pending
depends: [03-backend-api]
files:
  - path: web/frontend/src/api/buckets.ts
    action: modify
---

# Frontend Types and API: Bucket Interface and Link Functions

## Context
Updates TypeScript types to match new backend response and adds API functions for linking buckets to playlists.

## Files to Modify/Create
- web/frontend/src/api/buckets.ts (modify)

## Implementation Details

### Update Bucket interface:

```typescript
export interface Bucket {
  id: string;
  name: string;
  emoji_id: string | null;
  position: number;
  track_ids: number[];
  linked_playlist_id: number | null;  // NEW
  linked_playlist_name: string | null;  // NEW
}
```

### New types:

```typescript
export interface LinkBucketBody {
  playlist_id: number | null;
}

export interface BucketLinkResponse {
  playlist_id: number | null;
}
```

### New API functions:

```typescript
export async function linkBucket(bucketId: string, playlistId: number | null): Promise<void> {
  const response = await fetch(`${API_BASE}/${bucketId}/link`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ playlist_id: playlistId }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to link bucket');
  }
}

export async function getBucketLink(bucketId: string): Promise<BucketLinkResponse> {
  const response = await fetch(`${API_BASE}/${bucketId}/link`);
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to get bucket link');
  }
  return response.json();
}
```

## Verification

1. TypeScript compiles without errors: `cd web/frontend && pnpm tsc --noEmit`
2. Existing tests pass: `cd web/frontend && pnpm test`
3. Types match backend response (manually verify in browser devtools when running full app)
