import { apiRequest } from './client';

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
  duration_ms: number;        // Actual listening time (renamed from position_ms)
  end_reason: string | null;  // 'skip' | 'completed' | 'new_play'
}

export interface Stats {
  total_plays: number;
  total_minutes: number;  // Actual listening time
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
  return apiRequest<HistoryEntry[]>(`/history${query ? `?${query}` : ''}`);
}

export async function getStats(days: number = 30): Promise<Stats> {
  return apiRequest<Stats>(`/history/stats?days=${days}`);
}

export async function getTopTracks(
  limit: number = 10,
  days: number = 30
): Promise<TopTrack[]> {
  return apiRequest<TopTrack[]>(
    `/history/top-tracks?limit=${limit}&days=${days}`
  );
}
