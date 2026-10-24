import { describe, expect, it } from 'vitest';
import {
  emptyMessage,
  lastActivity,
  matchesQuery,
  selectPickerPlaylists,
  sortPlaylists,
} from './playlistPicker';
import type { PickerPlaylist } from './playlistPicker';

function pl(id: number, name: string, extra: Partial<PickerPlaylist> = {}): PickerPlaylist {
  return { id, name, type: 'manual', track_count: 10, library: 'local', pin_order: null, ...extra };
}

const LIST: PickerPlaylist[] = [
  pl(1, 'Pinned Bangers', { pin_order: 0, track_count: 5, updated_at: '2026-01-01 00:00:00' }),
  pl(2, 'deep house', { track_count: 40, last_played_at: '2026-10-20 10:00:00', updated_at: '2026-09-01 00:00:00' }),
  pl(3, 'Afro', { track_count: 40, description: 'Amapiano and afro house' }),
  pl(4, 'Track 10', { updated_at: '2026-10-22 08:00:00' }),
  pl(5, 'Track 9'),
];

const ids = (list: PickerPlaylist[]): number[] => list.map((p) => p.id);

describe('matchesQuery', () => {
  it('matches everything for a blank query', () => {
    expect(matchesQuery(LIST[0], '   ')).toBe(true);
  });

  it('is case-insensitive and needs every term', () => {
    expect(matchesQuery(LIST[1], 'HOUSE deep')).toBe(true);
    expect(matchesQuery(LIST[1], 'house techno')).toBe(false);
  });

  it('searches the description too', () => {
    expect(matchesQuery(LIST[2], 'amapiano')).toBe(true);
  });
});

describe('lastActivity', () => {
  it('takes the newer of played and updated', () => {
    expect(lastActivity(LIST[1])).toBe('2026-10-20 10:00:00');
    expect(lastActivity(LIST[3])).toBe('2026-10-22 08:00:00');
  });

  it('is empty when neither is set', () => {
    expect(lastActivity(LIST[4])).toBe('');
  });
});

describe('sortPlaylists', () => {
  it('recent: newest activity first, undated last in server order', () => {
    expect(ids(sortPlaylists(LIST, 'recent'))).toEqual([4, 2, 1, 3, 5]);
  });

  it('name: case-insensitive with natural numbers', () => {
    expect(ids(sortPlaylists(LIST, 'name'))).toEqual([3, 2, 1, 5, 4]);
  });

  it('size: biggest first, ties by name', () => {
    expect(ids(sortPlaylists(LIST, 'size'))).toEqual([3, 2, 5, 4, 1]);
  });

  it('does not mutate the input', () => {
    const before = ids(LIST);
    sortPlaylists(LIST, 'name');
    expect(ids(LIST)).toEqual(before);
  });
});

describe('selectPickerPlaylists', () => {
  it('filters then sorts', () => {
    expect(ids(selectPickerPlaylists(LIST, 'track', 'name'))).toEqual([5, 4]);
  });
});

describe('emptyMessage', () => {
  it('names the query while searching', () => {
    expect(emptyMessage(' afro ', 'No playlists')).toBe('No playlists match "afro"');
  });

  it('falls back to the screen copy', () => {
    expect(emptyMessage('', 'No playlists')).toBe('No playlists');
  });
});
