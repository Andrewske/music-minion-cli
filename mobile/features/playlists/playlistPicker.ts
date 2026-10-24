/**
 * Pure search + sort for the shared PlaylistPicker (Compare and Organize).
 */
import type { Playlist } from '@music-minion/shared';

/**
 * `/playlists` also returns timestamps the shared `Playlist` type leaves out.
 * SQLite writes them as "YYYY-MM-DD HH:MM:SS", so string order is time order.
 */
export interface PickerPlaylist extends Playlist {
  last_played_at?: string | null;
  updated_at?: string | null;
}

export type PlaylistSort = 'recent' | 'name' | 'size';

export const PLAYLIST_SORTS: readonly { key: PlaylistSort; label: string }[] = [
  { key: 'recent', label: 'Recent' },
  { key: 'name', label: 'A–Z' },
  { key: 'size', label: 'Size' },
];

/** Every whitespace-separated term must appear in the name or description. */
export function matchesQuery(playlist: Playlist, query: string): boolean {
  const terms = query.toLowerCase().split(/\s+/).filter((t) => t.length > 0);
  const haystack = `${playlist.name} ${playlist.description ?? ''}`.toLowerCase();
  return terms.every((t) => haystack.includes(t));
}

/** Newest activity timestamp, or '' when the playlist has none. */
export function lastActivity(playlist: PickerPlaylist): string {
  const played = playlist.last_played_at ?? '';
  const updated = playlist.updated_at ?? '';
  return played > updated ? played : updated;
}

function compareRecent(a: PickerPlaylist, b: PickerPlaylist): number {
  const ta = lastActivity(a);
  const tb = lastActivity(b);
  if (ta === tb) return 0;
  return ta > tb ? -1 : 1;
}

function compareName(a: Playlist, b: Playlist): number {
  return a.name.localeCompare(b.name, undefined, { sensitivity: 'base', numeric: true });
}

function compareSize(a: Playlist, b: Playlist): number {
  return b.track_count - a.track_count || compareName(a, b);
}

const COMPARATORS: Record<PlaylistSort, (a: PickerPlaylist, b: PickerPlaylist) => number> = {
  recent: compareRecent,
  name: compareName,
  size: compareSize,
};

/** New sorted array; ties keep the server order (pinned first). */
export function sortPlaylists(playlists: readonly PickerPlaylist[], sort: PlaylistSort): PickerPlaylist[] {
  return [...playlists].sort(COMPARATORS[sort]);
}

/** What the picker list shows for the current query and sort. */
export function selectPickerPlaylists(
  playlists: readonly PickerPlaylist[],
  query: string,
  sort: PlaylistSort,
): PickerPlaylist[] {
  return sortPlaylists(playlists.filter((p) => matchesQuery(p, query)), sort);
}

/** Empty-list copy: a no-match message while searching, else the screen's own. */
export function emptyMessage(query: string, fallback: string): string {
  const trimmed = query.trim();
  return trimmed ? `No playlists match "${trimmed}"` : fallback;
}
