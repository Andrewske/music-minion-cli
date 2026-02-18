export interface TrackInfo {
  id: number;
  title: string;
  artist?: string;
  album?: string;
  year?: number;
  bpm?: number;
  genre?: string;
  rating: number;
  comparison_count: number;
  wins: number;
  losses: number;
  duration?: number;
  has_waveform: boolean;
  emojis?: string[];
  // Playlist ranking fields
  playlist_rating?: number;
  playlist_comparison_count?: number;
  global_rating?: number;
}

export interface Playlist {
  id: number;
  name: string;
  type: 'manual' | 'smart';
  description?: string;
  track_count: number;
  library: string;
  pin_order: number | null;
}

export interface ComparisonPair {
  track_a: TrackInfo;
  track_b: TrackInfo;
}

export interface ComparisonProgress {
  compared: number;
  total: number;
  percentage: number;
}

export interface ComparisonRequest {
  playlist_id: number;
}

export interface RecordComparisonRequest {
  playlist_id: number;
  track_a_id: number;
  track_b_id: number;
  winner_id: number;
}

export interface ComparisonResponse {
  pair: ComparisonPair | null;
  progress: ComparisonProgress;
}

export interface WaveformData {
  version: number;
  channels: number;
  sample_rate: number;
  samples_per_pixel: number;
  bits: number;
  length: number;
  peaks: number[];
}

export interface GenreStat {
  genre: string;
  track_count: number;
  average_rating: number;
  total_comparisons: number;
}

export interface LeaderboardEntry {
  track_id: number;
  title: string;
  artist?: string;
  rating: number;
  comparison_count: number;
  wins: number;
  losses: number;
}

export interface StatsResponse {
  total_comparisons: number;
  compared_tracks: number;
  total_tracks: number;
  coverage_percent: number;
  average_comparisons_per_day: number;
  estimated_days_to_coverage: number | null;
  prioritized_tracks?: number | null;
  prioritized_coverage_percent?: number | null;
  prioritized_estimated_days?: number | null;
  top_genres: GenreStat[];
  leaderboard: LeaderboardEntry[];
}

export interface FoldersResponse {
  root: string;
  folders: string[];
}

export interface PlaylistBasicStats {
  total_tracks: number;
  total_duration: number;
  avg_duration: number;
  year_min?: number;
  year_max?: number;
}

export interface PlaylistEloAnalysis {
  total_tracks: number;
  rated_tracks: number;
  compared_tracks: number;
  coverage_percentage: number;
  avg_playlist_rating: number;
  min_playlist_rating: number;
  max_playlist_rating: number;
  avg_global_rating: number;
  min_global_rating: number;
  max_global_rating: number;
  avg_playlist_comparisons: number;
  total_playlist_comparisons: number;
}

export interface PlaylistQualityMetrics {
  total_tracks: number;
  missing_bpm: number;
  missing_key: number;
  missing_year: number;
  missing_genre: number;
  without_tags: number;
  completeness_score: number;
}

export interface ArtistStat {
  artist: string;
  track_count: number;
}

export interface GenreDistribution {
  genre: string;
  count: number;
  percentage: number;
}

export interface PlaylistTrackEntry {
  id: number;
  title: string;
  artist?: string;
  rating: number;
  wins: number;
  losses: number;
  comparison_count: number;
  emojis?: string[];
}

export interface PlaylistTracksResponse {
  playlist_name: string;
  tracks: PlaylistTrackEntry[];
}

export interface PlaylistStatsResponse {
  playlist_name: string;
  playlist_type: string;
  basic: PlaylistBasicStats;
  elo: PlaylistEloAnalysis;
  quality: PlaylistQualityMetrics;
  top_artists: ArtistStat[];
  top_genres: GenreDistribution[];
  avg_comparisons_per_day: number;
  estimated_days_to_full_coverage: number | null;
}