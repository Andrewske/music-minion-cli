import { getDefaultApiClient } from './client';

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

export interface SyncResponse {
  tracks_synced: number;
  playlists_synced: number;
  likes_synced: number;
  errors: string[];
  last_synced_at: string;
}

export interface SyncStatus {
  last_synced_at: string | null;
  track_count: number;
}

export async function getSoundCloudPlaylists(): Promise<SoundCloudPlaylist[]> {
  return getDefaultApiClient().request<SoundCloudPlaylist[]>('/soundcloud/playlists');
}

export async function matchPlaylist(playlistId: string): Promise<MatchPlaylistResponse> {
  return getDefaultApiClient().request<MatchPlaylistResponse>('/soundcloud/match-playlist', {
    method: 'POST',
    body: JSON.stringify({ playlist_id: playlistId }),
  });
}

export async function createPlaylistFromMatches(
  request: CreatePlaylistRequest
): Promise<CreatePlaylistResponse> {
  return getDefaultApiClient().request<CreatePlaylistResponse>('/soundcloud/create-playlist-from-matches', {
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

export async function searchTracks(query: string, limit = 20): Promise<TrackSearchResult[]> {
  return getDefaultApiClient().request<TrackSearchResult[]>(
    `/tracks/search?q=${encodeURIComponent(query)}&limit=${limit}`
  );
}

export async function getSoundCloudSyncStatus(): Promise<SyncStatus> {
  return getDefaultApiClient().request<SyncStatus>('/soundcloud/sync/status');
}

// ============================================================================
// Match Candidates
// ============================================================================

export interface MatchCandidateTrack {
  id: number;
  title: string | null;
  artist: string | null;
}

export interface MatchCandidate {
  id: number;
  local_track: MatchCandidateTrack;
  sc_track: MatchCandidateTrack;
  score: number;
  scoring_path: string | null;
}

export interface MatchCandidateStats {
  pending: number;
  accepted: number;
  rejected: number;
  total: number;
}

export interface GetMatchingCandidatesParams {
  page?: number;
  pageSize?: number;
  minScore?: number;
  maxScore?: number;
}

export async function getMatchingCandidates(
  params?: GetMatchingCandidatesParams
): Promise<MatchCandidate[]> {
  const qs = new URLSearchParams();
  if (params?.page !== undefined) qs.set('page', String(params.page));
  if (params?.pageSize !== undefined) qs.set('page_size', String(params.pageSize));
  if (params?.minScore !== undefined) qs.set('min_score', String(params.minScore));
  if (params?.maxScore !== undefined) qs.set('max_score', String(params.maxScore));
  const query = qs.toString() ? `?${qs.toString()}` : '';
  return getDefaultApiClient().request<MatchCandidate[]>(
    `/soundcloud/matching/candidates${query}`
  );
}

export async function acceptCandidate(candidateId: number): Promise<{ ok: boolean }> {
  return getDefaultApiClient().request<{ ok: boolean }>('/soundcloud/matching/accept', {
    method: 'POST',
    body: JSON.stringify({ candidate_id: candidateId }),
  });
}

export async function rejectCandidate(candidateId: number): Promise<{ ok: boolean }> {
  return getDefaultApiClient().request<{ ok: boolean }>('/soundcloud/matching/reject', {
    method: 'POST',
    body: JSON.stringify({ candidate_id: candidateId }),
  });
}

export async function getMatchingStats(): Promise<MatchCandidateStats> {
  return getDefaultApiClient().request<MatchCandidateStats>('/soundcloud/matching/stats');
}

export async function syncSoundCloudLibrary(): Promise<SyncResponse> {
  try {
    return await getDefaultApiClient().request<SyncResponse>('/soundcloud/sync', {
      method: 'POST',
    });
  } catch (err) {
    if (err instanceof Error && err.message.includes('401')) {
      throw new Error('SOUNDCLOUD_AUTH_EXPIRED');
    }
    throw err;
  }
}
