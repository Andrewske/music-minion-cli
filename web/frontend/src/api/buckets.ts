import { apiRequest } from './client';

const API_BASE = '/api/buckets';

// Types
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

// Session operations

export async function createOrResumeSession(playlistId: number): Promise<BucketSession> {
  const response = await fetch(`${API_BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ playlist_id: playlistId }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    try {
      const error = JSON.parse(errorText);
      throw new Error(error.detail || 'Failed to create/resume session');
    } catch {
      throw new Error(`Failed to create/resume session: ${response.status} ${errorText.substring(0, 100)}`);
    }
  }

  return response.json();
}

export async function getSession(sessionId: string): Promise<BucketSession> {
  return apiRequest<BucketSession>(`/buckets/sessions/${sessionId}`);
}

export async function discardSession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`, { method: 'DELETE' });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to discard session');
  }
}

export async function applySession(sessionId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/apply`, { method: 'POST' });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to apply session');
  }
}

// Bucket operations

export async function createBucket(sessionId: string, body: CreateBucketBody): Promise<Bucket> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/buckets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to create bucket');
  }

  return response.json();
}

export async function updateBucket(bucketId: string, body: UpdateBucketBody): Promise<Bucket> {
  const response = await fetch(`${API_BASE}/${bucketId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to update bucket');
  }

  return response.json();
}

export async function deleteBucket(bucketId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${bucketId}`, { method: 'DELETE' });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to delete bucket');
  }
}

export async function moveBucket(bucketId: string, direction: 'up' | 'down'): Promise<void> {
  const response = await fetch(`${API_BASE}/${bucketId}/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ direction }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to move bucket');
  }
}

export async function shuffleBucket(bucketId: string): Promise<number[]> {
  const response = await fetch(`${API_BASE}/${bucketId}/shuffle`, { method: 'POST' });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to shuffle bucket');
  }
  const data = await response.json();
  return data.track_ids;
}

// Track assignment

export async function assignTrack(bucketId: string, trackId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/${bucketId}/tracks/${trackId}`, { method: 'POST' });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to assign track');
  }
}

export async function unassignTrack(bucketId: string, trackId: number): Promise<void> {
  const response = await fetch(`${API_BASE}/${bucketId}/tracks/${trackId}`, { method: 'DELETE' });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to unassign track');
  }
}

export async function reorderTracks(bucketId: string, trackIds: number[]): Promise<void> {
  const response = await fetch(`${API_BASE}/${bucketId}/tracks/reorder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ track_ids: trackIds }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to reorder tracks');
  }
}
