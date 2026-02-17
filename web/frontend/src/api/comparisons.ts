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

export async function selectTrack(trackId: number, isPlaying: boolean): Promise<void> {
  await apiRequest('/comparisons/select-track', {
    method: 'POST',
    body: JSON.stringify({ track_id: trackId, is_playing: isPlaying }),
  });
}