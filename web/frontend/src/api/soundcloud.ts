/**
 * SoundCloud Import Wizard API functions.
 * Supports matching SoundCloud playlists to local library and creating playlists from matches.
 */

import { apiRequest } from './client';

// Types matching backend schemas.py

export interface SoundCloudPlaylist {
  id: string;
  name: string;
  track_count: number;
}

export interface ScPlaylistMatch {
  sc_track_id: string;
  sc_title: string;
  sc_artist: string;
  local_track_id: number | null;
  local_title: string | null;
  local_artist: string | null;
  confidence: number;
  is_approved: boolean;
  is_missing: boolean;
  sc_position?: number;
  // Frontend-only state (not sent to backend):
  isFixed?: boolean;
  isConfirmed?: boolean;
}

export interface MatchPlaylistResponse {
  playlist_name: string;
  sc_playlist_id: string;
  matches: ScPlaylistMatch[];
  auto_approved_count: number;
  needs_review_count: number;
}

export interface CreatePlaylistRequest {
  playlist_name: string;
  sc_playlist_id: string;
  matches: ScPlaylistMatch[];
}

export interface CreatePlaylistResponse {
  playlist_id: number;
  track_count: number;
}

export interface TrackSearchResult {
  id: number;
  title: string;
  artist: string | null;
  album: string | null;
}

/**
 * Fetch user's SoundCloud playlists.
 * Requires SoundCloud authentication.
 */
export async function getSoundCloudPlaylists(): Promise<SoundCloudPlaylist[]> {
  return apiRequest<SoundCloudPlaylist[]>('/soundcloud/playlists');
}

/**
 * Match a SoundCloud playlist's tracks to local library.
 * Returns matches sorted by confidence (lowest first for review).
 */
export async function matchPlaylist(playlistId: string): Promise<MatchPlaylistResponse> {
  return apiRequest<MatchPlaylistResponse>('/soundcloud/match-playlist', {
    method: 'POST',
    body: JSON.stringify({ playlist_id: playlistId }),
  });
}

/**
 * Create a local playlist from matched tracks.
 * Excludes tracks marked as missing.
 */
export async function createPlaylistFromMatches(
  request: CreatePlaylistRequest
): Promise<CreatePlaylistResponse> {
  return apiRequest<CreatePlaylistResponse>('/soundcloud/create-playlist-from-matches', {
    method: 'POST',
    body: JSON.stringify({
      playlist_name: request.playlist_name,
      sc_playlist_id: request.sc_playlist_id,
      matches: request.matches.map((m) => ({
        sc_track_id: m.sc_track_id,
        sc_title: m.sc_title,
        sc_artist: m.sc_artist,
        local_track_id: m.local_track_id,
        local_title: m.local_title,
        local_artist: m.local_artist,
        confidence: m.confidence,
        is_approved: m.is_approved,
        is_missing: m.is_missing,
        sc_position: m.sc_position,
      })),
    }),
  });
}

/**
 * Search local tracks for autocomplete.
 * Used when fixing low-confidence matches.
 */
export async function searchTracks(query: string, limit = 20): Promise<TrackSearchResult[]> {
  return apiRequest<TrackSearchResult[]>(
    `/tracks/search?q=${encodeURIComponent(query)}&limit=${limit}`
  );
}
