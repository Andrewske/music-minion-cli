import type { Playlist, PlaylistStatsResponse, PlaylistTracksResponse } from '../types';

import { apiRequest } from './client';

const API_BASE = '/api';

export async function createPlaylist(name: string, description: string = ''): Promise<Playlist> {
  const response = await fetch(`${API_BASE}/playlists`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  });

  if (!response.ok) {
    try {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create playlist');
    } catch (e) {
      // If JSON parsing fails (e.g., HTML error page), use generic message
      throw new Error('Failed to create playlist');
    }
  }

  return response.json();
}

export async function getPlaylistStats(playlistId: number): Promise<PlaylistStatsResponse> {
  return apiRequest<PlaylistStatsResponse>(`/playlists/${playlistId}/stats`);
}

export async function getPlaylistTracks(playlistId: number): Promise<PlaylistTracksResponse> {
  return apiRequest<PlaylistTracksResponse>(`/playlists/${playlistId}/tracks`);
}