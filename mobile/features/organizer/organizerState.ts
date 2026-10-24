/**
 * Pure helpers for the mobile organizer session screen.
 */
import type { BucketSession, Playlist, TrackName } from '@music-minion/shared';
import { formatTrackLabel } from '@music-minion/shared';

/** Every track id the session displays (unassigned + all buckets), sorted and unique. */
export function sessionTrackIds(session: BucketSession | undefined): number[] {
  if (!session) return [];
  const ids = new Set<number>(session.unassigned_track_ids);
  session.buckets.forEach((b) => b.track_ids.forEach((id) => ids.add(id)));
  return [...ids].sort((a, b) => a - b);
}

/** id -> "Artist — Title" lookup map. */
export function buildTrackLabels(tracks: readonly TrackName[] | undefined): Map<number, string> {
  return new Map((tracks ?? []).map((t) => [t.id, formatTrackLabel(t)]));
}

/** Label for a track id: placeholder while names load, explicit marker if the track no longer exists. */
export function trackLabel(labels: Map<number, string>, trackId: number, isLoaded: boolean): string {
  return labels.get(trackId) ?? (isLoaded ? `Missing track #${trackId}` : 'Loading…');
}

export interface SessionCounts {
  total: number;
  assigned: number;
  unassigned: number;
  buckets: number;
}

/** Header counts. A track in several buckets counts once toward `assigned`. */
export function sessionCounts(session: BucketSession | undefined): SessionCounts {
  if (!session) return { total: 0, assigned: 0, unassigned: 0, buckets: 0 };
  const assigned = new Set<number>();
  session.buckets.forEach((b) => b.track_ids.forEach((id) => assigned.add(id)));
  const unassigned = session.unassigned_track_ids.length;
  return { total: assigned.size + unassigned, assigned: assigned.size, unassigned, buckets: session.buckets.length };
}

/** Organize opens any playlist with tracks, smart or manual. */
export function selectOrganizablePlaylists(playlists: readonly Playlist[] | undefined): Playlist[] {
  return (playlists ?? []).filter((p) => p.track_count > 0);
}

/** Picker row subtitle, e.g. "Smart · 42 tracks". */
export function organizeSubtitle(playlist: Playlist): string {
  const size = playlist.track_count === 1 ? '1 track' : `${playlist.track_count} tracks`;
  return `${playlist.type === 'smart' ? 'Smart' : 'Manual'} · ${size}`;
}
