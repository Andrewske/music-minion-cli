import { describe, expect, it } from 'vitest';
import {
  artworkUrl,
  findArtistId,
  isDateBucket,
  primaryArtistName,
  trackActions,
  trackRowSubtitle,
} from './trackRow';

describe('isDateBucket', () => {
  it('matches month buckets', () => {
    expect(isDateBucket('Oct 26')).toBe(true);
    expect(isDateBucket('Sep 2026')).toBe(true);
    expect(isDateBucket(" sept '25 ")).toBe(true);
  });

  it('leaves real album names alone', () => {
    expect(isDateBucket('Octane 26')).toBe(false);
    expect(isDateBucket('Discovery')).toBe(false);
    expect(isDateBucket('May')).toBe(false);
  });
});

describe('trackRowSubtitle', () => {
  it('drops a date-bucket album', () => {
    expect(trackRowSubtitle({ artist: 'Zomboy', album: 'Oct 26' })).toBe('Zomboy');
  });

  it('keeps a real album', () => {
    expect(trackRowSubtitle({ artist: 'Daft Punk', album: 'Discovery' })).toBe('Daft Punk · Discovery');
  });

  it('falls back when the artist is missing or blank', () => {
    expect(trackRowSubtitle({})).toBe('Unknown Artist');
    expect(trackRowSubtitle({ artist: '  ', album: '' })).toBe('Unknown Artist');
  });
});

describe('artworkUrl', () => {
  it('appends the artwork path to the api base', () => {
    expect(artworkUrl('https://pi:8446/api', 42)).toBe('https://pi:8446/api/tracks/42/artwork');
    expect(artworkUrl('https://pi:8446/api/', 42)).toBe('https://pi:8446/api/tracks/42/artwork');
  });
});

describe('trackActions', () => {
  it('offers Go to artist only when there is an artist', () => {
    expect(trackActions({ artist: 'Zomboy' }).map((a) => a.key)).toEqual(['play', 'artist']);
    expect(trackActions({}).map((a) => a.key)).toEqual(['play']);
    expect(trackActions({ artist: ' ' }).map((a) => a.key)).toEqual(['play']);
  });
});

describe('primaryArtistName', () => {
  it('takes the first credited name', () => {
    expect(primaryArtistName('Skrillex; Young Miko')).toBe('Skrillex');
    expect(primaryArtistName('Subtronics, Inéz')).toBe('Subtronics');
    expect(primaryArtistName('Wiley ft. Someone')).toBe('Wiley');
    expect(primaryArtistName('Crankdat x HEYZ')).toBe('Crankdat');
    expect(primaryArtistName('Xanu')).toBe('Xanu');
  });
});

describe('findArtistId', () => {
  const artists = [
    { id: null, display_name: 'Local Only' },
    { id: 7, display_name: 'Skrillex' },
    { id: 9, display_name: 'Skrillex; Young Miko' },
    { id: 3, display_name: 'Zomboy' },
  ];

  it('prefers an exact case-insensitive match', () => {
    expect(findArtistId(artists, 'skrillex; young miko')).toBe(9);
    expect(findArtistId(artists, 'ZOMBOY')).toBe(3);
  });

  it('falls back to the first credited name', () => {
    expect(findArtistId(artists, 'Skrillex & Alvin Risk')).toBe(7);
  });

  it('returns null for artists without a page', () => {
    expect(findArtistId(artists, 'Local Only')).toBeNull();
    expect(findArtistId(artists, 'Nobody')).toBeNull();
  });
});
