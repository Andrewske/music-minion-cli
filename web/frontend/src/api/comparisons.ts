import { apiRequest } from './client';
import type {
  ComparisonRequest,
  ComparisonResponse,
  RecordComparisonRequest,
} from '../types';

export async function startComparison(playlistId: number): Promise<ComparisonResponse> {
  return apiRequest('/comparisons/start', {
    method: 'POST',
    body: JSON.stringify({ playlist_id: playlistId } as ComparisonRequest),
  });
}

export async function recordComparison(
  request: RecordComparisonRequest
): Promise<ComparisonResponse> {
  return apiRequest('/comparisons/record', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function activateComparisonMode(): Promise<void> {
  await apiRequest('/comparisons/activate', { method: 'POST' });
}

export async function deactivateComparisonMode(): Promise<void> {
  await apiRequest('/comparisons/activate', { method: 'DELETE' });
}
