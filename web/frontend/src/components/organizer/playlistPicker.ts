import type { Playlist } from '../../types';

const MAX_RESULTS = 50;

/** Manual playlists matching the query: ones holding the track first, then pinned, then by name. */
export function filterPlaylists(
  playlists: Playlist[],
  query: string,
  memberIds: ReadonlySet<number>,
  excludeId: number,
): Playlist[] {
  const q = query.trim().toLowerCase();
  const rank = (p: Playlist): number => (memberIds.has(p.id) ? 0 : p.pin_order !== null ? 1 : 2);
  return playlists
    .filter((p) => p.type === 'manual' && p.id !== excludeId && p.name.toLowerCase().includes(q))
    .sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name))
    .slice(0, MAX_RESULTS);
}

/** True when the query names a playlist that doesn't exist yet (names compare case-insensitively). */
export function canCreatePlaylist(playlists: Playlist[], query: string): boolean {
  const q = query.trim().toLowerCase();
  return q !== '' && !playlists.some((p) => p.name.toLowerCase() === q);
}
