import type { PlaylistStatsResponse, PlaylistTracksResponse } from '../types';

import { apiRequest } from './client';

export async function getPlaylistStats(playlistId: number): Promise<PlaylistStatsResponse> {
  return apiRequest<PlaylistStatsResponse>(`/playlists/${playlistId}/stats`);
}

export async function getPlaylistTracks(playlistId: number): Promise<PlaylistTracksResponse> {
  return apiRequest<PlaylistTracksResponse>(`/playlists/${playlistId}/tracks`);
}