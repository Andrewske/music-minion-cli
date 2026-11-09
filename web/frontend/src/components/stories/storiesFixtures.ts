import type { StoriesArtist, StoriesResponse, StoriesTrack } from '../../api/stories';

export const makeTrack = (soundcloudId: string, overrides: Partial<StoriesTrack> = {}): StoriesTrack => ({
  soundcloud_id: soundcloudId,
  title: `Track ${soundcloudId}`,
  artist_name: `Uploader ${soundcloudId}`,
  artwork_url: null,
  permalink_url: null,
  duration_ms: 200_000,
  kind: 'repost',
  activity_at: '2026-11-08T02:00:00Z',
  local_track_id: null,
  score: null,
  decision: null,
  listened: false,
  ...overrides,
});

export const makeArtist = (id: number, tracks: StoriesTrack[], overrides: Partial<StoriesArtist> = {}): StoriesArtist => ({
  discovery_artist_id: id,
  display_name: `Artist ${id}`,
  slug: `artist-${id}`,
  avatar_url: null,
  latest_activity_at: '2026-11-08T02:00:00Z',
  unheard_count: tracks.filter((track) => !track.listened).length,
  tracks,
  ...overrides,
});

export const makeResponse = (artists: StoriesArtist[]): StoriesResponse => ({
  generated_at: '2026-11-08T20:00:00Z',
  artists,
});
