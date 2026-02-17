// web/frontend/src/api/builder.ts

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

export interface Filter {
  field: string;
  operator: string;
  value: string;
  conjunction: 'AND' | 'OR';
}

export interface Track {
  id: number;
  title: string;
  artist?: string;
  album?: string;
  genre?: string;
  year?: number;
  bpm?: number;
  key_signature?: string;
  duration?: number;
  local_path?: string;
  elo_rating?: number;
  emojis?: string[];
}

export interface TrackActionResponse {
  success: boolean;
  // Note: No next_track - call getNextCandidate() separately
}

export const builderApi = {
  // Context Activation
  activateBuilderMode: async (playlistId: number): Promise<void> => {
    const res = await fetch(`${API_BASE}/builder/activate/${playlistId}`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error('Failed to activate builder mode');
  },

  deactivateBuilderMode: async (): Promise<void> => {
    const res = await fetch(`${API_BASE}/builder/activate`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error('Failed to deactivate builder mode');
  },

  // Track Operations
  addTrack: async (playlistId: number, trackId: number): Promise<TrackActionResponse> => {
    const res = await fetch(`${API_BASE}/builder/add/${playlistId}/${trackId}`, {
      method: 'POST'
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || 'Failed to add track');
    }
    return res.json();
  },

  skipTrack: async (playlistId: number, trackId: number): Promise<TrackActionResponse> => {
    const res = await fetch(`${API_BASE}/builder/skip/${playlistId}/${trackId}`, {
      method: 'POST'
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || 'Failed to skip track');
    }
    return res.json();
  },

  getNextCandidate: async (playlistId: number, excludeTrackId?: number): Promise<Track | null> => {
    const url = excludeTrackId
      ? `${API_BASE}/builder/candidates/${playlistId}/next?exclude_track_id=${excludeTrackId}`
      : `${API_BASE}/builder/candidates/${playlistId}/next`;
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to get next candidate');
    return res.json();
  },

  // Filter Management
  getFilters: async (playlistId: number): Promise<Filter[]> => {
    const res = await fetch(`${API_BASE}/builder/filters/${playlistId}`);
    if (!res.ok) throw new Error('Failed to get filters');
    const data = await res.json();
    return data.filters;
  },

  updateFilters: async (playlistId: number, filters: Filter[]): Promise<void> => {
    const res = await fetch(`${API_BASE}/builder/filters/${playlistId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filters })
    });
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.detail || 'Failed to update filters');
    }
  },

  clearFilters: async (playlistId: number): Promise<void> => {
    const res = await fetch(`${API_BASE}/builder/filters/${playlistId}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error('Failed to clear filters');
  },

  // Review
  getCandidates: async (
    playlistId: number,
    limit: number = 100,
    offset: number = 0,
    sortField: string = 'artist',
    sortDirection: string = 'asc'
  ): Promise<{ candidates: Track[]; total: number; hasMore: boolean }> => {
    const res = await fetch(
      `${API_BASE}/builder/candidates/${playlistId}?limit=${limit}&offset=${offset}&sort_field=${sortField}&sort_direction=${sortDirection}`
    );
    if (!res.ok) throw new Error('Failed to get candidates');
    const data = await res.json();
    return {
      ...data,
      hasMore: offset + data.candidates.length < data.total,
    };
  },

  getSkippedTracks: async (playlistId: number): Promise<Track[]> => {
    const res = await fetch(`${API_BASE}/builder/skipped/${playlistId}`);
    if (!res.ok) throw new Error('Failed to get skipped tracks');
    const data = await res.json();
    return data.skipped;
  },

  unskipTrack: async (playlistId: number, trackId: number): Promise<void> => {
    const res = await fetch(`${API_BASE}/builder/skipped/${playlistId}/${trackId}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error('Failed to unskip track');
  }
};
