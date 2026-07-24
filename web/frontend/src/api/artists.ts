// Re-export from shared package
export {
  getArtists, getArtist, getArtistLibraryTracks, getLocalArtistLibraryTracks,
  getArtistConnections, unfollowArtist, createMatchOverride,
  deleteMatchOverride, getPareto, syncFollowings, syncFeed, getFeedSyncStatus,
} from '@music-minion/shared';
export type {
  ArtistStats, ArtistDetail, ArtistLibraryTrack, FeedEvent, LibraryTrack, MatchOverride,
  PlaylistRef, PlaylistLibrary, ConnectionTrack, ConnectionRelation, ArtistConnection,
  ParetoResult, FeedSyncState, FirstLovedTrack, UnfollowResult, FollowingsSyncResult,
  GetArtistsOptions, CreateMatchOverrideBody,
} from '@music-minion/shared';
