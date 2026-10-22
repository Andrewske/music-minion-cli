import { getDefaultApiClient } from './client';

/** Tag review (#48): metadata-cleanup tracks the nightly ingest left pending. */

/** model = run A, alt = run B, gold = keep current tags, exclude = skip (leave file alone). */
export type CleanupVerdict = 'model' | 'alt' | 'edited' | 'gold' | 'unclear' | 'exclude';

export interface CleanupView {
  title: string;
  credited_artists: string[];
  remixers: string[];
}

export type CleanupField = keyof CleanupView;

export interface CleanupRaw {
  title: string;
  uploader: string | null;
  description: string;
  filename: string;
  url: string | null;
  genre?: string | null;
}

export interface CleanupRow {
  /** Path relative to ~/Music/EDM; the ledger's track id. */
  id: string;
  current: CleanupView;
  a: CleanupView;
  b: CleanupView;
  /** True per field where runs A and B disagree (case-insensitive). */
  diff: Record<CleanupField, boolean>;
  confidence: number;
  notes: string;
  raw: CleanupRaw;
  /** Marked unclear earlier; still pending, sorted last. */
  unclear: boolean;
  /** music-minion tracks.id for playback; null if the file isn't imported yet. */
  track_id: number | null;
}

export interface PendingCleanupResponse {
  rows: CleanupRow[];
  count: number;
}

export interface CleanupDecisionRequest {
  id: string;
  verdict: CleanupVerdict;
  /** Required for 'edited'. */
  expected?: CleanupView;
}

export interface CleanupDecisionResponse {
  id: string;
  status: 'applied' | 'kept' | 'pending';
  written: boolean;
  verdict: CleanupVerdict;
  db_refreshed: boolean;
  track_id: number | null;
  /** Pending tracks left after this decision. */
  remaining: number;
}

export async function getPendingCleanup(): Promise<PendingCleanupResponse> {
  return getDefaultApiClient().request<PendingCleanupResponse>('/cleanup/pending');
}

export async function getPendingCleanupCount(): Promise<{ count: number }> {
  return getDefaultApiClient().request<{ count: number }>('/cleanup/pending/count');
}

export async function decideCleanup(request: CleanupDecisionRequest): Promise<CleanupDecisionResponse> {
  return getDefaultApiClient().post<CleanupDecisionResponse>('/cleanup/pending/decision', request);
}
