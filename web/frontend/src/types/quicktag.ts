export interface DimensionPair {
  id: string;
  leftEmoji: string;
  rightEmoji: string;
  label: string;
  description?: string;
  sortOrder: number;
}

export interface TrackDimensionVote {
  dimensionId: string;
  vote: -1 | 0 | 1;
  votedAt: string;
}
