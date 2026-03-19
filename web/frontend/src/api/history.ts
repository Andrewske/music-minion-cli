// Re-export from shared package
export { getHistory, getStats, getTopTracks } from '@music-minion/shared';
export type { HistoryEntry, TopTrack, Stats, SourceFilter } from '@music-minion/shared';

// Re-export the history-specific TrackInfo (different shape from main TrackInfo)
export type { HistoryTrackInfo as TrackInfo } from '@music-minion/shared';
