import { describe, expect, it } from 'vitest';
import { ageLabel, asTier, formatFollowers, scoreChips, soundcloudSearchUrl } from './format';
import { makeSuggestion } from './followSuggestionsFixtures';

const NOW = Date.parse('2026-11-11T12:00:00Z');
const daysAgo = (d: number): string => new Date(NOW - d * 86_400_000).toISOString();

describe('scoreChips', () => {
  it('builds the liked / remixes / last like / posts chips', () => {
    const s = makeSuggestion({ last_liked_at: daysAgo(21) });
    expect(scoreChips(s, NOW)).toEqual(['12 liked', '4 remixes', 'last like 3 wk ago', 'posts 4/mo']);
  });

  it('skips zero counts and missing activity', () => {
    const s = makeSuggestion({
      evidence: { uploaded: 0, original: 0, remixer: 1, feat: 2, remixed_by_others: 0, kept: 3 },
      activity: null,
    });
    expect(scoreChips(s, NOW)).toEqual(['1 remix', '2 feat', '3 kept']);
  });

  it('flags quiet accounts', () => {
    const s = makeSuggestion({ activity: { uploads_90d: 0, reposts_90d: 0, last_active_at: null } });
    expect(scoreChips(s, NOW)).toContain('quiet 90d');
  });
});

describe('format helpers', () => {
  it('coarsens ages', () => {
    expect(ageLabel(daysAgo(0), NOW)).toBe('today');
    expect(ageLabel(daysAgo(5), NOW)).toBe('5d ago');
    expect(ageLabel(daysAgo(90), NOW)).toBe('3 mo ago');
    expect(ageLabel(daysAgo(800), NOW)).toBe('2 yr ago');
  });

  it('encodes SoundCloud search names', () => {
    expect(soundcloudSearchUrl('Dirt Monkey & Co')).toBe('https://soundcloud.com/search/people?q=Dirt%20Monkey%20%26%20Co');
  });

  it('formats followers and validates tiers', () => {
    expect(formatFollowers(1_500)).toBe('1.5k');
    expect(formatFollowers(2_000_000)).toBe('2m');
    expect(asTier('A')).toBe('A');
    expect(asTier('')).toBeNull();
  });
});
