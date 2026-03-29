// Re-export from shared package
export {
  triggerDiscoverySync, getDiscoverySyncStatus, getLastSync, seedArtists,
} from '@music-minion/shared';
export type {
  DiscoverySyncJob, DiscoverySyncStatus, LastSync,
} from '@music-minion/shared';
