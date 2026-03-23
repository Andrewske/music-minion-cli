// API client
export { createApiClient, setDefaultApiClient, getDefaultApiClient, ApiError } from './api/client';
export type { ApiClient } from './api/client';

// Types
export type {
  TrackInfo, Playlist, ComparisonPair, ComparisonProgress,
  ComparisonRequest, RecordComparisonRequest, ComparisonResponse,
  WaveformData, GenreStat, FoldersResponse,
  PlaylistBasicStats, PlaylistEloAnalysis, PlaylistQualityMetrics,
  ArtistStat, GenreDistribution, PlaylistTrackEntry,
  PlaylistTracksResponse, PlaylistStatsResponse,
} from './types/index';
export type { DimensionPair, TrackDimensionVote } from './types/quicktag';

// API modules — re-export selectively to avoid name collisions
export { startComparison, recordComparison, activateComparisonMode, deactivateComparisonMode } from './api/comparisons';
export {
  createPlaylist, getPlaylistStats, getPlaylistTracks, getSmartFilters,
  updateSmartFilters, pinPlaylist, unpinPlaylist, reorderPinnedPlaylist,
  deletePlaylist, skipSmartPlaylistTrack, unskipSmartPlaylistTrack,
  getSmartPlaylistSkippedTracks, getSmartPlaylistTracks, getPlaylistsByLibrary,
} from './api/playlists';
export {
  getStreamUrl, getWaveformData, checkStreamAvailable, archiveTrack,
  refreshWaveform, purgeSoundcloudWaveforms, getFolders,
} from './api/tracks';
export { getHistory, getStats, getTopTracks } from './api/history';
export type { HistoryEntry, TopTrack, Stats, SourceFilter } from './api/history';
export type { TrackInfo as HistoryTrackInfo } from './api/history';
export {
  listGenres, renameGenre, assignGenreEmoji, deleteGenre,
  getTrackGenres, updateTrackGenres,
} from './api/genres';
export type { GenreInfo, TrackGenre } from './api/genres';
export {
  getTopEmojis, getAllEmojis, getRecentEmojis, searchEmojis,
  addEmojiToTrack, removeEmojiFromTrack, updateEmojiMetadata, deleteCustomEmoji,
} from './api/emojis';
export type { EmojiInfo, TrackEmoji } from './api/emojis';
export {
  getSoundCloudPlaylists, matchPlaylist, createPlaylistFromMatches,
  searchTracks, getSoundCloudSyncStatus, syncSoundCloudLibrary,
} from './api/soundcloud';
export type {
  SoundCloudPlaylist, ScPlaylistMatch, MatchPlaylistResponse,
  CreatePlaylistRequest, CreatePlaylistResponse, TrackSearchResult,
  SyncResponse, SyncStatus,
} from './api/soundcloud';
export { builderApi } from './api/builder';
export type { Filter, Track, TrackActionResponse } from './api/builder';
export * from './api/buckets';

// Stores
export { createPlayerStore, getCurrentPosition } from './stores/createPlayerStore';
export type { PlatformDeps, PlayerStore, PlayerState, PlayerActions, PlayContext, Device } from './stores/createPlayerStore';
export { createWebStorageAdapter, createMemoryStorageAdapter } from './stores/storage';
export type { StorageAdapter } from './stores/storage';
