/**
 * Pure helpers for track rows (Home, History) and the Home long-press sheet.
 */
import type { ArtistStats, Track } from '@music-minion/shared';

/**
 * Library imports file tracks into month buckets, so `album` is often just
 * "Oct 26" and repeats down the whole list. Those aren't worth a subtitle.
 */
const MONTH =
  '(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)';
const DATE_BUCKET = new RegExp(`^${MONTH}\\.? '?\\d{2}(?:\\d{2})?$`, 'i');

export const isDateBucket = (album: string): boolean => DATE_BUCKET.test(album.trim());

/** "Artist · Album", dropping a date-bucket album. */
export const trackRowSubtitle = (track: Pick<Track, 'artist' | 'album'>): string => {
  const artist = track.artist?.trim() || 'Unknown Artist';
  const album = track.album?.trim();
  if (!album || isDateBucket(album)) return artist;
  return `${artist} · ${album}`;
};

/** Same artwork endpoint the full player uses; baseUrl already ends in /api. */
export const artworkUrl = (baseUrl: string, trackId: number): string =>
  `${baseUrl.replace(/\/+$/, '')}/tracks/${trackId}/artwork`;

export type TrackActionKey = 'play' | 'artist';

export interface TrackAction {
  key: TrackActionKey;
  label: string;
}

/** Long-press actions for a track. Only actions with an existing API. */
export const trackActions = (track: Pick<Track, 'artist'>): TrackAction[] => {
  const actions: TrackAction[] = [{ key: 'play', label: 'Play now' }];
  if (track.artist?.trim()) actions.push({ key: 'artist', label: 'Go to artist' });
  return actions;
};

const normalize = (name: string): string => name.trim().toLowerCase();

/** First credited name: "Skrillex; Young Miko" → "Skrillex". */
export const primaryArtistName = (artist: string): string =>
  artist.split(/;|,|\s+(?:feat\.?|ft\.?|x|&|vs\.?)\s+/i)[0]?.trim() ?? artist.trim();

/**
 * Artist-page id for a track's artist string: exact name first, then the
 * first credited name. null when the artist has no discovery page.
 */
export const findArtistId = (
  artists: readonly Pick<ArtistStats, 'id' | 'display_name'>[],
  artist: string
): number | null => {
  const linked = artists.filter((a): a is { id: number; display_name: string } => a.id !== null);
  for (const name of [artist, primaryArtistName(artist)]) {
    const match = linked.find((a) => normalize(a.display_name) === normalize(name));
    if (match) return match.id;
  }
  return null;
};
