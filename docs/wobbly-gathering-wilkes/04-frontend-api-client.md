---
task: 04-frontend-api-client
status: pending
depends: [03-bucket-backend-api]
files:
  - path: web/frontend/src/api/buckets.ts
    action: create
---

# Frontend API Client for Buckets

## Context
Create TypeScript API client functions to interact with the bucket backend API, following existing patterns from other API modules.

## Files to Modify/Create
- web/frontend/src/api/buckets.ts (new)

## Implementation Details

### Types

```typescript
export interface BucketSession {
  id: string;
  playlist_id: number;
  status: 'active' | 'applied' | 'discarded';
  buckets: Bucket[];
  unassigned_track_ids: number[];
}

export interface Bucket {
  id: string;
  name: string;
  emoji_id: string | null;
  position: number;
  track_ids: number[];
}

export interface CreateSessionBody {
  playlist_id: number;
}

export interface CreateBucketBody {
  name: string;
  emoji_id?: string;
}

export interface UpdateBucketBody {
  name?: string;
  emoji_id?: string | null;
}

export interface MoveBucketBody {
  direction: 'up' | 'down';
}

export interface ReorderTracksBody {
  track_ids: number[];
}
```

### API Functions

```typescript
const API_BASE = '/api/buckets';

// Session operations
export async function createOrResumeSession(playlistId: number): Promise<BucketSession> {
  const res = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ playlist_id: playlistId }),
  });
  if (!res.ok) throw new Error('Failed to create/resume session');
  return res.json();
}

export async function getSession(sessionId: string): Promise<BucketSession> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`);
  if (!res.ok) throw new Error('Failed to get session');
  return res.json();
}

export async function discardSession(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to discard session');
}

export async function applySession(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/apply`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to apply session');
}

// Bucket operations
export async function createBucket(sessionId: string, body: CreateBucketBody): Promise<Bucket> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/buckets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to create bucket');
  return res.json();
}

export async function updateBucket(bucketId: string, body: UpdateBucketBody): Promise<Bucket> {
  const res = await fetch(`${API_BASE}/${bucketId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to update bucket');
  return res.json();
}

export async function deleteBucket(bucketId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/${bucketId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to delete bucket');
}

export async function moveBucket(bucketId: string, direction: 'up' | 'down'): Promise<void> {
  const res = await fetch(`${API_BASE}/${bucketId}/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ direction }),
  });
  if (!res.ok) throw new Error('Failed to move bucket');
}

export async function shuffleBucket(bucketId: string): Promise<number[]> {
  const res = await fetch(`${API_BASE}/${bucketId}/shuffle`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to shuffle bucket');
  const data = await res.json();
  return data.track_ids;
}

// Track assignment
export async function assignTrack(bucketId: string, trackId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/${bucketId}/tracks/${trackId}`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to assign track');
}

export async function unassignTrack(bucketId: string, trackId: number): Promise<void> {
  const res = await fetch(`${API_BASE}/${bucketId}/tracks/${trackId}`, { method: 'DELETE' });
  if (!res.ok) throw new Error('Failed to unassign track');
}

export async function reorderTracks(bucketId: string, trackIds: number[]): Promise<void> {
  const res = await fetch(`${API_BASE}/${bucketId}/tracks/reorder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ track_ids: trackIds }),
  });
  if (!res.ok) throw new Error('Failed to reorder tracks');
}
```

## Verification
```bash
# TypeScript compilation check
cd web/frontend && npx tsc --noEmit

# Import check - add to a test component temporarily
# import * as bucketsApi from './api/buckets';
# console.log(bucketsApi);
```
