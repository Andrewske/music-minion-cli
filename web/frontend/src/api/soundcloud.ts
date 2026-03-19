// Re-export from shared package
export {
  getSoundCloudPlaylists, matchPlaylist, createPlaylistFromMatches,
  searchTracks, getSoundCloudSyncStatus, syncSoundCloudLibrary,
} from '@music-minion/shared';
export type {
  SoundCloudPlaylist, ScPlaylistMatch, MatchPlaylistResponse,
  CreatePlaylistRequest, CreatePlaylistResponse, TrackSearchResult,
  SyncResponse, SyncStatus,
} from '@music-minion/shared';
