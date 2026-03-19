// API client
export { createApiClient, setDefaultApiClient, getDefaultApiClient, ApiError } from './api/client.js';
export type { ApiClient } from './api/client.js';

// Types
export type * from './types/index.js';
export type * from './types/quicktag.js';

// API modules — re-export selectively to avoid name collisions
export { startComparison, recordComparison, activateComparisonMode, deactivateComparisonMode } from './api/comparisons.js';
export {
  createPlaylist, getPlaylistStats, getPlaylistTracks, getSmartFilters,
  updateSmartFilters, pinPlaylist, unpinPlaylist, reorderPinnedPlaylist,
  deletePlaylist, skipSmartPlaylistTrack, unskipSmartPlaylistTrack,
  getSmartPlaylistSkippedTracks, getSmartPlaylistTracks, getPlaylistsByLibrary,
} from './api/playlists.js';
export {
  getStreamUrl, getWaveformData, checkStreamAvailable, archiveTrack,
  refreshWaveform, purgeSoundcloudWaveforms, getFolders,
} from './api/tracks.js';
export { getHistory, getStats, getTopTracks } from './api/history.js';
export type { HistoryEntry, TopTrack, Stats, SourceFilter } from './api/history.js';
export type { TrackInfo as HistoryTrackInfo } from './api/history.js';
export {
  listGenres, renameGenre, assignGenreEmoji, deleteGenre,
  getTrackGenres, updateTrackGenres,
} from './api/genres.js';
export type { GenreInfo, TrackGenre } from './api/genres.js';
export {
  getTopEmojis, getAllEmojis, getRecentEmojis, searchEmojis,
  addEmojiToTrack, removeEmojiFromTrack, updateEmojiMetadata, deleteCustomEmoji,
} from './api/emojis.js';
export type { EmojiInfo, TrackEmoji } from './api/emojis.js';
export {
  getSoundCloudPlaylists, matchPlaylist, createPlaylistFromMatches,
  searchTracks, getSoundCloudSyncStatus, syncSoundCloudLibrary,
} from './api/soundcloud.js';
export type {
  SoundCloudPlaylist, ScPlaylistMatch, MatchPlaylistResponse,
  CreatePlaylistRequest, CreatePlaylistResponse, TrackSearchResult,
  SyncResponse, SyncStatus,
} from './api/soundcloud.js';
export { builderApi } from './api/builder.js';
export type { Filter, Track, TrackActionResponse } from './api/builder.js';
export * from './api/buckets.js';

// Stores
export { createPlayerStore, getCurrentPosition } from './stores/createPlayerStore.js';
export type { PlatformDeps, PlayerStore, PlayerState, PlayerActions, PlayContext, Device } from './stores/createPlayerStore.js';
export { createWebStorageAdapter, createMemoryStorageAdapter } from './stores/storage.js';
export type { StorageAdapter } from './stores/storage.js';
