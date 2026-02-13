import { apiRequest } from './client';
import type {
  StartSessionRequest,
  StartSessionResponse,
  RecordComparisonRequest,
  RecordComparisonResponse,
  ComparisonPair,
} from '../types';

export async function startSession(
  request: StartSessionRequest
): Promise<StartSessionResponse> {
  return apiRequest('/comparisons/session', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function getNextPair(sessionId: string): Promise<ComparisonPair> {
  return apiRequest(`/comparisons/next-pair?session_id=${sessionId}`);
}

export async function recordComparison(
  request: RecordComparisonRequest
): Promise<RecordComparisonResponse> {
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