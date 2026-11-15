/**
 * Which playlists the full player's "Add" sheet offers for a track.
 */
import type { Track } from '@music-minion/shared';
import type { PickerPlaylist } from '../playlists/playlistPicker';

/**
 * Manual playlists only (smart ones are rule-built). Local playlists export to
 * M3U/Serato crates and need a file, so a stream-only track skips them; the
 * server enforces the same rule.
 */
export function addablePlaylists(
  playlists: readonly PickerPlaylist[],
  track: Pick<Track, 'local_path'>,
): PickerPlaylist[] {
  const hasFile = Boolean(track.local_path);
  return playlists.filter((p) => p.type === 'manual' && (hasFile || p.library !== 'local'));
}

/** Row subtitle: "Already added", or "<n> tracks · <library>". */
export function playlistTargetSubtitle(playlist: PickerPlaylist, containing: ReadonlySet<number>): string {
  if (containing.has(playlist.id)) return 'Already added';
  const count = playlist.track_count === 1 ? '1 track' : `${playlist.track_count} tracks`;
  return `${count} · ${playlist.library}`;
}
