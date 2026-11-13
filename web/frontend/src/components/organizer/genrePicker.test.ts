import { describe, expect, it } from 'vitest';
import type { GenreInfo } from '../../api/genres';
import { canCreateGenre, filterGenres, withPrimaryGenre } from './genrePicker';

const genre = (id: number, name: string, track_count: number): GenreInfo => ({
  id, name, track_count, emoji_id: null, created_at: '',
});

const GENRES = [
  genre(1, 'deep house', 40),
  genre(2, 'house', 10),
  genre(3, 'tech house', 90),
  genre(4, 'garage', 5),
];

describe('filterGenres', () => {
  it('lists most-used first for an empty query', () => {
    expect(filterGenres(GENRES, '').map((g) => g.id)).toEqual([3, 1, 2, 4]);
  });

  it('ranks prefix matches above substring matches', () => {
    expect(filterGenres(GENRES, 'Hou').map((g) => g.id)).toEqual([2, 3, 1]);
  });

  it('returns nothing when no genre matches', () => {
    expect(filterGenres(GENRES, 'dnb')).toEqual([]);
  });
});

describe('canCreateGenre', () => {
  it('allows a new name', () => {
    expect(canCreateGenre(GENRES, 'Breaks')).toBe(true);
  });

  it('rejects an existing name regardless of case and padding', () => {
    expect(canCreateGenre(GENRES, '  House ')).toBe(false);
  });

  it('rejects a blank query', () => {
    expect(canCreateGenre(GENRES, '   ')).toBe(false);
  });
});

describe('withPrimaryGenre', () => {
  it('puts the pick first and keeps the rest in order', () => {
    expect(withPrimaryGenre([5, 6, 7], 7)).toEqual([7, 5, 6]);
  });

  it('adds a genre the track did not have', () => {
    expect(withPrimaryGenre([5], 9)).toEqual([9, 5]);
  });
});
