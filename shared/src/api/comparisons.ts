import { getDefaultApiClient } from './client';
import type {
  ComparisonRequest,
  ComparisonResponse,
  RecordComparisonRequest,
} from '../types/index';

export async function startComparison(playlistId: number): Promise<ComparisonResponse> {
  return getDefaultApiClient().request('/comparisons/start', {
    method: 'POST',
    body: JSON.stringify({ playlist_id: playlistId } as ComparisonRequest),
  });
}

export async function recordComparison(
  request: RecordComparisonRequest
): Promise<ComparisonResponse> {
  return getDefaultApiClient().request('/comparisons/record', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function activateComparisonMode(): Promise<void> {
  await getDefaultApiClient().request('/comparisons/activate', { method: 'POST' });
}

export async function deactivateComparisonMode(): Promise<void> {
  await getDefaultApiClient().request('/comparisons/activate', { method: 'DELETE' });
}
