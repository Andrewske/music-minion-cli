// Re-export from shared package
export {
  getArtists, getArtist, unfollowArtist, createMatchOverride, deleteMatchOverride,
  getPareto, syncFollowings, syncFeed, getFeedSyncStatus,
} from '@music-minion/shared';
export type {
  ArtistStats, ArtistDetail, FeedEvent, LibraryTrack, MatchOverride,
  ParetoResult, FeedSyncState, FirstLovedTrack, UnfollowResult, FollowingsSyncResult,
  GetArtistsOptions, CreateMatchOverrideBody,
} from '@music-minion/shared';
