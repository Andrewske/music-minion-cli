import { getDefaultApiClient } from './client.js';

// === Types ===

export type SourceFilter = 'all' | 'local' | 'youtube' | 'soundcloud' | 'spotify';

export interface TrackInfo {
  id: number;
  title: string | null;
  artist: string | null;
  album: string | null;
  duration: number | null;
  local_path: string | null;
  emojis?: string[];
}

export interface HistoryEntry {
  id: number;
  track_id: number | null;
  track_title: string;
  track_artist: string;
  source_type: string;
  started_at: string;
  ended_at: string | null;
  duration_ms: number;
  end_reason: string | null;
}

export interface Stats {
  total_plays: number;
  total_minutes: number;
  unique_tracks: number;
}

export interface TopTrack {
  track_id: number;
  track_title: string;
  track_artist: string;
  play_count: number;
  total_duration_seconds: number;
}

// === API Functions ===

export async function getHistory(params: {
  limit?: number;
  offset?: number;
  startDate?: string;
  endDate?: string;
}): Promise<HistoryEntry[]> {
  const queryParams = new URLSearchParams();
  if (params.limit) queryParams.set('limit', String(params.limit));
  if (params.offset) queryParams.set('offset', String(params.offset));
  if (params.startDate) queryParams.set('start_date', params.startDate);
  if (params.endDate) queryParams.set('end_date', params.endDate);

  const query = queryParams.toString();
  return getDefaultApiClient().request<HistoryEntry[]>(`/history${query ? `?${query}` : ''}`);
}

export async function getStats(days: number = 30): Promise<Stats> {
  return getDefaultApiClient().request<Stats>(`/history/stats?days=${days}`);
}

export async function getTopTracks(
  limit: number = 10,
  days: number = 30
): Promise<TopTrack[]> {
  return getDefaultApiClient().request<TopTrack[]>(
    `/history/top-tracks?limit=${limit}&days=${days}`
  );
}
