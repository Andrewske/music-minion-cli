import { apiRequest } from './client';

// === Types ===

export interface Station {
  id: number;
  name: string;
  playlist_id: number | null;
  mode: 'shuffle' | 'queue';
  is_active: boolean;
}

export interface TrackInfo {
  id: number;
  title: string | null;
  artist: string | null;
  album: string | null;
  duration: number | null;
  local_path: string | null;
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
  mode: 'shuffle' | 'queue' = 'shuffle'
): Promise<Station> {
  const body: CreateStationRequest = { name, mode };
  if (playlistId !== undefined) {
    body.playlist_id = playlistId;
  }
  return apiRequest<Station>('/radio/stations', {
    method: 'POST',
    body: JSON.stringify(body),
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
