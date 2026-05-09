// Re-export from shared package
export {
  getSoundCloudPlaylists, matchPlaylist, createPlaylistFromMatches,
  searchTracks, getSoundCloudSyncStatus, syncSoundCloudLibrary,
  getMatchingCandidates, acceptCandidate, rejectCandidate, getMatchingStats,
} from '@music-minion/shared';
export type {
  SoundCloudPlaylist, ScPlaylistMatch, MatchPlaylistResponse,
  CreatePlaylistRequest, CreatePlaylistResponse, TrackSearchResult,
  SyncResponse, SyncStatus,
  MatchCandidate, MatchCandidateTrack, MatchCandidateStats, GetMatchingCandidatesParams,
} from '@music-minion/shared';
