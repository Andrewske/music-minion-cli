import { describe, expect, it } from 'vitest';
import type { Playlist } from '../../types';
import { canCreatePlaylist, filterPlaylists } from './playlistPicker';

const playlist = (id: number, name: string, extra: Partial<Playlist> = {}): Playlist => ({
  id, name, type: 'manual', track_count: 0, library: 'local', pin_order: null, ...extra,
});

const PLAYLISTS = [
  playlist(1, 'Warmup'),
  playlist(2, 'Peak Time', { pin_order: 0 }),
  playlist(3, 'Smart Bangers', { type: 'smart' }),
  playlist(4, 'Afters'),
  playlist(5, 'Organizing Now'),
];

describe('filterPlaylists', () => {
  it('drops smart playlists and the excluded one', () => {
    const ids = filterPlaylists(PLAYLISTS, '', new Set(), 5).map((p) => p.id);
    expect(ids).not.toContain(3);
    expect(ids).not.toContain(5);
  });

  it('orders member playlists, then pinned, then by name', () => {
    expect(filterPlaylists(PLAYLISTS, '', new Set([1]), 5).map((p) => p.id)).toEqual([1, 2, 4]);
  });

  it('matches case-insensitive substrings', () => {
    expect(filterPlaylists(PLAYLISTS, 'TIME', new Set(), 5).map((p) => p.id)).toEqual([2]);
  });
});

describe('canCreatePlaylist', () => {
  it('allows a new name', () => {
    expect(canCreatePlaylist(PLAYLISTS, 'Closing')).toBe(true);
  });

  it('rejects an existing name regardless of case', () => {
    expect(canCreatePlaylist(PLAYLISTS, ' warmup ')).toBe(false);
  });

  it('rejects a blank query', () => {
    expect(canCreatePlaylist(PLAYLISTS, '  ')).toBe(false);
  });
});
