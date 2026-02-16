import type { Playlist, PlaylistStatsResponse, PlaylistTracksResponse } from '../types';
import type { Filter } from './builder';

import { apiRequest } from './client';

const API_BASE = '/api';

// Using direct fetch here for custom error handling (see builder.ts for similar pattern).
// Use apiRequest for simple GET/POST without special error handling needs.
export async function createPlaylist(name: string, description: string = ''): Promise<Playlist> {
  const response = await fetch(`${API_BASE}/playlists`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    try {
      const error = JSON.parse(errorText);
      throw new Error(error.detail || 'Failed to create playlist');
    } catch {
      // If JSON parsing fails (e.g., HTML error page), include status and preview
      throw new Error(`Failed to create playlist: ${response.status} ${errorText.substring(0, 100)}`);
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

export async function getSmartFilters(playlistId: number): Promise<Filter[]> {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}/filters`);
  if (!response.ok) throw new Error('Failed to fetch filters');
  const data = await response.json();
  return data.filters;
}

export async function updateSmartFilters(
  playlistId: number,
  filters: Filter[]
): Promise<Filter[]> {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}/filters`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(filters),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to update filters');
  }
  const data = await response.json();
  return data.filters;
}

export async function pinPlaylist(playlistId: number): Promise<{ playlist: Playlist }> {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}/pin`, {
    method: 'POST',
  });
  if (!response.ok) throw new Error('Failed to pin playlist');
  return response.json();
}

export async function unpinPlaylist(playlistId: number): Promise<{ playlist: Playlist }> {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}/pin`, {
    method: 'DELETE',
  });
  if (!response.ok) throw new Error('Failed to unpin playlist');
  return response.json();
}

export async function reorderPinnedPlaylist(
  playlistId: number,
  position: number
): Promise<{ playlist: Playlist }> {
  const response = await fetch(`${API_BASE}/playlists/${playlistId}/pin`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ position }),
  });
  if (!response.ok) throw new Error('Failed to reorder playlist');
  return response.json();
}