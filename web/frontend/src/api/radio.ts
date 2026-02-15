import { apiRequest } from './client';

// === Types ===

export type SourceFilter = 'all' | 'local' | 'youtube' | 'soundcloud' | 'spotify';

export interface Station {
  id: number;
  name: string;
  playlist_id: number;
  shuffle_enabled: boolean;
}

export interface TrackInfo {
  id: number;
  title: string | null;
  artist: string | null;
  album: string | null;
  duration: number | null;
  local_path: string | null;
  emojis?: string[];
}

export interface NowPlaying {
  track: TrackInfo;
  position_ms: number;
  station_id: number;
  station_name: string;
  source_type: string;
  upcoming: TrackInfo[];
}

export interface ScheduleEntry {
  id: number;
  station_id: number;
  start_time: string;
  end_time: string;
  target_station_id: number;
  position: number;
}

export interface CreateStationRequest {
  name: string;
  playlist_id?: number;
  mode?: 'shuffle' | 'queue';
  source_filter?: SourceFilter;
}

export interface HistoryEntry {
  id: number;
  station_id: number;
  station_name: string;
  track: TrackInfo;
  source_type: string;
  started_at: string; // ISO format
  ended_at: string | null;
  position_ms: number;
}

export interface StationStats {
  station_id: number;
  station_name: string;
  total_plays: number;
  total_minutes: number;
  unique_tracks: number;
  days_queried: number;
}

export interface TrackPlayStats {
  track: TrackInfo;
  play_count: number;
  total_duration_seconds: number;
}

// === API Functions ===

export async function getNowPlaying(): Promise<NowPlaying> {
  return apiRequest<NowPlaying>('/radio/now-playing');
}

export async function getStations(): Promise<Station[]> {
  return apiRequest<Station[]>('/radio/stations');
}

export async function getStation(stationId: number): Promise<Station> {
  return apiRequest<Station>(`/radio/stations/${stationId}`);
}

export async function createStation(
  name: string,
  playlistId?: number,
  mode: 'shuffle' | 'queue' = 'shuffle',
  sourceFilter: SourceFilter = 'all'
): Promise<Station> {
  const body: CreateStationRequest = { name, mode, source_filter: sourceFilter };
  if (playlistId !== undefined) {
    body.playlist_id = playlistId;
  }
  return apiRequest<Station>('/radio/stations', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function updateStation(
  stationId: number,
  updates: {
    name?: string;
    playlist_id?: number | null;
    mode?: 'shuffle' | 'queue';
    source_filter?: SourceFilter;
  }
): Promise<Station> {
  return apiRequest<Station>(`/radio/stations/${stationId}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}

export async function deleteStation(stationId: number): Promise<void> {
  await apiRequest<{ ok: boolean }>(`/radio/stations/${stationId}`, {
    method: 'DELETE',
  });
}

export async function activateStation(stationId: number): Promise<void> {
  await apiRequest<{ ok: boolean; message: string }>(
    `/radio/stations/${stationId}/activate`,
    { method: 'POST' }
  );
}

export async function deactivateStation(): Promise<void> {
  await apiRequest<{ ok: boolean; was_active: boolean }>(
    '/radio/stations/deactivate',
    { method: 'POST' }
  );
}

export async function getSchedule(stationId: number): Promise<ScheduleEntry[]> {
  return apiRequest<ScheduleEntry[]>(`/radio/stations/${stationId}/schedule`);
}

export async function createScheduleEntry(
  stationId: number,
  startTime: string,
  endTime: string,
  targetStationId: number
): Promise<ScheduleEntry> {
  return apiRequest<ScheduleEntry>(`/radio/stations/${stationId}/schedule`, {
    method: 'POST',
    body: JSON.stringify({
      start_time: startTime,
      end_time: endTime,
      target_station_id: targetStationId,
    }),
  });
}

export async function updateScheduleEntry(
  entryId: number,
  updates: {
    start_time?: string;
    end_time?: string;
    target_station_id?: number;
    position?: number;
  }
): Promise<ScheduleEntry> {
  return apiRequest<ScheduleEntry>(`/radio/schedule/${entryId}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}

export async function deleteScheduleEntry(entryId: number): Promise<void> {
  await apiRequest<{ ok: boolean }>(`/radio/schedule/${entryId}`, {
    method: 'DELETE',
  });
}

export async function reorderSchedule(
  stationId: number,
  entryIds: number[]
): Promise<void> {
  await apiRequest<{ ok: boolean }>(
    `/radio/stations/${stationId}/schedule/reorder`,
    {
      method: 'PUT',
      body: JSON.stringify(entryIds),
    }
  );
}

export async function getHistory(params: {
  stationId?: number;
  limit?: number;
  offset?: number;
  startDate?: string; // YYYY-MM-DD
  endDate?: string; // YYYY-MM-DD
}): Promise<HistoryEntry[]> {
  const queryParams = new URLSearchParams();
  if (params.stationId !== undefined) {
    queryParams.append('station_id', params.stationId.toString());
  }
  if (params.limit !== undefined) {
    queryParams.append('limit', params.limit.toString());
  }
  if (params.offset !== undefined) {
    queryParams.append('offset', params.offset.toString());
  }
  if (params.startDate) {
    queryParams.append('start_date', params.startDate);
  }
  if (params.endDate) {
    queryParams.append('end_date', params.endDate);
  }

  const query = queryParams.toString();
  return apiRequest<HistoryEntry[]>(`/radio/history${query ? `?${query}` : ''}`);
}

export async function getStationStats(
  stationId: number,
  days: number = 30
): Promise<StationStats> {
  return apiRequest<StationStats>(
    `/radio/stations/${stationId}/stats?days=${days}`
  );
}

export async function getTopTracks(
  stationId?: number,
  limit: number = 10,
  days: number = 30
): Promise<TrackPlayStats[]> {
  const queryParams = new URLSearchParams();
  if (stationId !== undefined) {
    queryParams.append('station_id', stationId.toString());
  }
  queryParams.append('limit', limit.toString());
  queryParams.append('days', days.toString());

  const query = queryParams.toString();
  return apiRequest<TrackPlayStats[]>(
    `/radio/top-tracks?${query}`
  );
}
