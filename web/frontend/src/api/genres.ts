import { apiRequest } from './client';

export interface GenreInfo {
  id: number;
  name: string;
  emoji_id: string | null;
  track_count: number;
  created_at: string;
}

export interface TrackGenre {
  id: number;
  name: string;
  emoji_id: string | null;
  position: number;
}

export async function listGenres(): Promise<GenreInfo[]> {
  return apiRequest<GenreInfo[]>('/genres');
}

export async function renameGenre(genreId: number, name: string): Promise<GenreInfo> {
  return apiRequest<GenreInfo>(`/genres/${genreId}`, {
    method: 'PUT',
    body: JSON.stringify({ name }),
  });
}

export async function assignGenreEmoji(
  genreId: number,
  emojiId: string | null
): Promise<GenreInfo> {
  return apiRequest<GenreInfo>(`/genres/${genreId}/emoji`, {
    method: 'PUT',
    body: JSON.stringify({ emoji_id: emojiId }),
  });
}

export async function deleteGenre(genreId: number): Promise<{ deleted: boolean }> {
  return apiRequest<{ deleted: boolean }>(`/genres/${genreId}`, {
    method: 'DELETE',
  });
}

export async function getTrackGenres(trackId: number): Promise<TrackGenre[]> {
  return apiRequest<TrackGenre[]>(`/tracks/${trackId}/genres`);
}

export async function updateTrackGenres(
  trackId: number,
  genreIds: number[]
): Promise<TrackGenre[]> {
  return apiRequest<TrackGenre[]>(`/tracks/${trackId}/genres`, {
    method: 'PUT',
    body: JSON.stringify({ genre_ids: genreIds }),
  });
}
