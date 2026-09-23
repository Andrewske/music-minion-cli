// API client
export { createApiClient, setDefaultApiClient, getDefaultApiClient, ApiError } from './api/client';
export type { ApiClient } from './api/client';

// Types
export type {
  TrackInfo, Playlist, ComparisonPair, ComparisonProgress,
  ComparisonRequest, RecordComparisonRequest, ComparisonResponse,
  WaveformData, GenreStat, FoldersResponse,
  PlaylistBasicStats, PlaylistEloAnalysis, PlaylistQualityMetrics,
  ArtistStat, GenreDistribution, PlaylistTrackEntry, TrackReposter,
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
export { fetchPlayerQueue } from './api/player';
export type { QueuePage } from './api/player';
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
  getMatchingCandidates, acceptCandidate, rejectCandidate, getMatchingStats,
} from './api/soundcloud';
export type {
  SoundCloudPlaylist, ScPlaylistMatch, MatchPlaylistResponse,
  CreatePlaylistRequest, CreatePlaylistResponse, TrackSearchResult,
  SyncResponse, SyncStatus,
  MatchCandidate, MatchCandidateTrack, MatchCandidateStats, GetMatchingCandidatesParams,
} from './api/soundcloud';
export { builderApi } from './api/builder';
export type { Filter, Track, TrackActionResponse } from './api/builder';
export * from './api/buckets';
export {
  getArtists, getArtist, getArtistLibraryTracks, getLocalArtistLibraryTracks,
  getArtistConnections, unfollowArtist, updateArtist, createMatchOverride,
  deleteMatchOverride, getPareto, syncFollowings, syncFeed, getFeedSyncStatus,
} from './api/artists';
export type {
  ArtistStats, ArtistDetail, ArtistLibraryTrack, FeedEvent, LibraryTrack, MatchOverride,
  PlaylistRef, PlaylistLibrary, ConnectionTrack, ConnectionRelation, ArtistConnection,
  ParetoResult, FeedSyncState, FirstLovedTrack, UnfollowResult, FollowingsSyncResult,
  GetArtistsOptions, CreateMatchOverrideBody, ArtistTier, UpdateArtistBody, UpdateArtistResult,
} from './api/artists';
export {
  triggerDiscoverySync, getDiscoverySyncStatus, getLastSync, seedArtists,
} from './api/discovery';
export type {
  DiscoverySyncJob, DiscoverySyncStatus, LastSync,
} from './api/discovery';
export {
  FEED_PAGE_SIZE, FEED_RANK_PRESETS, feedRatingToDecision,
  getFeedItemDecision, getFeedItemUploader, getFeedEventAt,
  getFeedItemBestRank, normalizeFeedItem, applyFeedDecision, mergeFeedDecisionResponse,
  isFeedSyncPending, isFeedSyncFailed, hasPendingFeedSync,
  getFeed, rateFeedItem, materializeFeedItem,
  startFeedBackfill,
} from './api/feed';
export type {
  FeedSource, FeedSort, FeedRankPreset, FeedRating, FeedDecision, FeedItemStatus,
  FeedActionStatus, FeedArtist, FeedActionState, FeedItem, FeedPage,
  GetFeedParams, RateFeedItemOptions, RateFeedItemResponse,
  MaterializeFeedItemResponse,
} from './api/feed';

// Playback error policy (shared window/breaker/retry decision logic)
export {
  recordError, clearErrorWindow, isBreakerTripped, decidePlaybackError,
  initialErrorWindow, ERROR_WINDOW_MS, ERROR_THRESHOLD, PLAYBACK_BREAKER_MESSAGE,
  shouldSuppressPrunedSkip, PRUNE_SUPPRESSION_WINDOW_MS,
} from './playback/errorPolicy';
export type { ErrorWindowState, PlaybackErrorDecision } from './playback/errorPolicy';

// SoundCloud reauth detection (503 stream probe on playback error)
export {
  probeStreamForReauth, isReauthDetail,
  SOUNDCLOUD_REAUTH_DETAIL, SOUNDCLOUD_REAUTH_MESSAGE, REAUTH_PROBE_TIMEOUT_MS,
} from './playback/reauthProbe';

// Stores
export { createPlayerStore, getCurrentPosition } from './stores/createPlayerStore';
export type { PlatformDeps, PlayerStore, PlayerState, PlayerActions, PlayContext, Device, SyncStatePayload } from './stores/createPlayerStore';
export { createWebStorageAdapter, createMemoryStorageAdapter } from './stores/storage';
export type { StorageAdapter } from './stores/storage';
