import { describe, expect, it } from 'vitest';
import type { PickerPlaylist } from '../playlists/playlistPicker';
import { addablePlaylists, playlistTargetSubtitle } from './playlistTargets';

const playlist = (id: number, type: 'manual' | 'smart', library: string, trackCount = 3): PickerPlaylist => ({
  id,
  name: `P${id}`,
  type,
  library,
  track_count: trackCount,
  pin_order: null,
});

const all = [playlist(1, 'manual', 'local'), playlist(2, 'smart', 'local'), playlist(3, 'manual', 'soundcloud')];

describe('addablePlaylists', () => {
  it('keeps manual playlists, local ones only for tracks with a file', () => {
    expect(addablePlaylists(all, { local_path: '/music/a.opus' }).map((p) => p.id)).toEqual([1, 3]);
    expect(addablePlaylists(all, {}).map((p) => p.id)).toEqual([3]);
  });
});

describe('playlistTargetSubtitle', () => {
  it('marks playlists that already hold the track', () => {
    expect(playlistTargetSubtitle(playlist(1, 'manual', 'local'), new Set([1]))).toBe('Already added');
  });

  it('shows size and library otherwise', () => {
    expect(playlistTargetSubtitle(playlist(3, 'manual', 'soundcloud', 1), new Set())).toBe('1 track · soundcloud');
    expect(playlistTargetSubtitle(playlist(3, 'manual', 'soundcloud', 40), new Set())).toBe('40 tracks · soundcloud');
  });
});
