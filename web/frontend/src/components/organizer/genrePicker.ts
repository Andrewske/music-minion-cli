import type { GenreInfo } from '../../api/genres';

const MAX_RESULTS = 50;

/** Mirrors the backend's normalize_genre_name (trim + lowercase). */
export function normalizeGenreName(name: string): string {
  return name.trim().toLowerCase();
}

/** Substring match; prefix matches first, then most-used. Empty query lists the most-used. */
export function filterGenres(genres: GenreInfo[], query: string): GenreInfo[] {
  const q = normalizeGenreName(query);
  const rank = (g: GenreInfo): number => (q && g.name.startsWith(q) ? 0 : 1);
  return genres
    .filter((g) => g.name.includes(q))
    .sort((a, b) => rank(a) - rank(b) || b.track_count - a.track_count || a.name.localeCompare(b.name))
    .slice(0, MAX_RESULTS);
}

/** True when the query names a genre that doesn't exist yet. */
export function canCreateGenre(genres: GenreInfo[], query: string): boolean {
  const q = normalizeGenreName(query);
  return q !== '' && !genres.some((g) => g.name === q);
}

/** Make `pickedId` the primary genre, keeping the track's other genres after it. */
export function withPrimaryGenre(currentIds: number[], pickedId: number): number[] {
  return [pickedId, ...currentIds.filter((id) => id !== pickedId)];
}
