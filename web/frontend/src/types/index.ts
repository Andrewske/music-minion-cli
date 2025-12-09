export interface TrackInfo {
  id: number;
  title: string;
  artist: string;
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
}

export interface ComparisonPair {
  track_a: TrackInfo;
  track_b: TrackInfo;
  session_id: string;
}

export interface StartSessionRequest {
  source_filter?: string;
  genre_filter?: string;
  year_filter?: string;
  playlist_id?: number;
}

export interface StartSessionResponse {
  session_id: string;
  total_tracks: number;
  pair: ComparisonPair;
}

export interface RecordComparisonRequest {
  session_id: string;
  track_a_id: number;
  track_b_id: number;
  winner_id: number;
}

export interface RecordComparisonResponse {
  success: boolean;
  comparisons_done: number;
  next_pair?: ComparisonPair;
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