import { describe, expect, it } from 'vitest';
import type { Bucket, BucketSession, Playlist } from '@music-minion/shared';
import {
  buildTrackLabels,
  organizeSubtitle,
  selectOrganizablePlaylists,
  sessionCounts,
  sessionTrackIds,
  trackLabel,
} from './organizerState';

function bucket(id: string, trackIds: number[]): Bucket {
  return {
    id,
    name: id,
    emoji_id: null,
    position: 0,
    track_ids: trackIds,
    linked_playlist_id: null,
    linked_playlist_name: null,
    linked_playlist_soundcloud_id: null,
  };
}

const session: BucketSession = {
  id: 's1',
  playlist_id: 1,
  status: 'active',
  buckets: [bucket('a', [5, 2]), bucket('b', [2, 9])],
  unassigned_track_ids: [7, 1],
};

describe('sessionTrackIds', () => {
  it('unions unassigned and bucket tracks, sorted and unique', () => {
    expect(sessionTrackIds(session)).toEqual([1, 2, 5, 7, 9]);
  });

  it('is empty without a session', () => {
    expect(sessionTrackIds(undefined)).toEqual([]);
  });
});

describe('sessionCounts', () => {
  it('counts multi-bucket tracks once', () => {
    expect(sessionCounts(session)).toEqual({ total: 5, assigned: 3, unassigned: 2, buckets: 2 });
  });
});

describe('track labels', () => {
  it('maps ids to labels and falls back while loading', () => {
    const labels = buildTrackLabels([{ id: 1, title: 'Song', artist: 'Band' }]);
    expect(trackLabel(labels, 1, true)).toBe('Band — Song');
    expect(trackLabel(labels, 2, false)).toBe('Loading…');
    expect(trackLabel(labels, 2, true)).toBe('Missing track #2');
  });
});

describe('organize picker helpers', () => {
  const playlist = (id: number, type: Playlist['type'], track_count: number): Playlist => ({
    id, name: `P${id}`, type, track_count, library: 'local', pin_order: null,
  });

  it('keeps smart and manual playlists that have tracks', () => {
    const list = [playlist(1, 'manual', 0), playlist(2, 'smart', 3), playlist(3, 'manual', 1)];
    expect(selectOrganizablePlaylists(list).map((p) => p.id)).toEqual([2, 3]);
    expect(selectOrganizablePlaylists(undefined)).toEqual([]);
  });

  it('labels the type and size', () => {
    expect(organizeSubtitle(playlist(1, 'smart', 42))).toBe('Smart · 42 tracks');
    expect(organizeSubtitle(playlist(2, 'manual', 1))).toBe('Manual · 1 track');
  });
});
