import type { StoriesDecision, StoriesTrackKind } from '../../api/stories';

export const STORIES_VERDICT_LABELS: Record<StoriesDecision, string> = {
  keep: 'Liked',
  not_quite: 'Not quite',
  nope: 'Skipped',
};

export const ACTIVITY_LABELS: Record<StoriesTrackKind, string> = {
  repost: 'reposted a track',
  upload: 'uploaded a track',
};

const UNITS: ReadonlyArray<readonly [string, number]> = [
  ['day', 86_400_000],
  ['hour', 3_600_000],
  ['minute', 60_000],
];

/** "18 hours ago" style; "just now" under a minute, "" for unparseable input. */
export function formatTimeAgo(iso: string, now: number = Date.now()): string {
  const time = new Date(iso).getTime();
  if (Number.isNaN(time)) return '';
  const elapsed = Math.max(0, now - time);
  const unit = UNITS.find(([, ms]) => elapsed >= ms);
  if (!unit) return 'just now';
  const count = Math.floor(elapsed / unit[1]);
  return `${count} ${unit[0]}${count === 1 ? '' : 's'} ago`;
}

export function formatDuration(ms: number): string {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(totalSec / 60)}:${String(totalSec % 60).padStart(2, '0')}`;
}

/** SoundCloud serves 100px "-large" artwork by default; the hero wants 500px. */
export const largeArtwork = (url: string | null): string | null =>
  url ? url.replace(/-large(\.\w+)$/, '-t500x500$1') : null;

/** Real permalink without SC's ?utm_* junk; the widget player resolves bare ids when no permalink is known. */
export function soundCloudUrl(track: { soundcloud_id: string; permalink_url: string | null }): string {
  if (track.permalink_url) return track.permalink_url.split('?')[0];
  const apiUrl = encodeURIComponent(`https://api.soundcloud.com/tracks/${track.soundcloud_id}`);
  return `https://w.soundcloud.com/player/?url=${apiUrl}`;
}
