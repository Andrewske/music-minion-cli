import { describe, expect, it } from 'vitest';
import type { FeedArtist, FeedItem } from '@music-minion/shared';
import {
  feedAttributions,
  formatKeepScore,
  formatOthers,
  formatRank,
  isLikelyKeep,
  pickLeadReposter,
  RANK_OPTIONS,
  rankChipLabel,
  rankFromKey,
  rankKey,
  repostAttribution,
  SOURCE_OPTIONS,
  sourceChipLabel,
  sourceFromKey,
  uploadAttribution,
} from './feedFormat';

const artist = (slug: string, ranking: number | null): FeedArtist => ({
  id: 1,
  soundcloud_id: null,
  display_name: slug.toUpperCase(),
  slug,
  avatar_url: null,
  ranking,
});

const item = (overrides: Partial<FeedItem> = {}): FeedItem => ({
  id: '7',
  soundcloud_id: '7',
  local_track_id: null,
  title: 'Track',
  artwork_url: null,
  permalink_url: null,
  duration_ms: 10_000,
  genre: null,
  event_at: '2026-09-12T00:00:00Z',
  uploaded_at: null,
  released_at: null,
  sources: ['repost'],
  uploader: null,
  reposters: [],
  best_reposter_rank: null,
  reposter_count: 0,
  current_decision: null,
  decided_at: null,
  action_state: { like: null, monthly_playlist: null, error: null },
  keep_probability: null,
  prediction_model_version: null,
  prediction_explanation: null,
  ...overrides,
});

describe('rank and count labels', () => {
  it('formats ranks and skips unranked artists', () => {
    expect(formatRank(150)).toBe('#150');
    expect(formatRank(null)).toBeNull();
    expect(formatRank(undefined)).toBeNull();
  });

  it('pluralizes others and hides zero', () => {
    expect(formatOthers(0)).toBeNull();
    expect(formatOthers(1)).toBe('+1 other');
    expect(formatOthers(5)).toBe('+5 others');
  });
});

describe('pickLeadReposter', () => {
  it('names the best-ranked reposter even when listed later', () => {
    const lead = pickLeadReposter([artist('a', null), artist('b', 300), artist('c', 150)]);
    expect(lead?.slug).toBe('c');
  });

  it('keeps API order for ties and all-unranked lists', () => {
    expect(pickLeadReposter([artist('a', 50), artist('b', 50)])?.slug).toBe('a');
    expect(pickLeadReposter([artist('a', null), artist('b', null)])?.slug).toBe('a');
    expect(pickLeadReposter([])).toBeNull();
  });
});

describe('attribution lines', () => {
  it('builds "Reposted by FESTIVILLAINZ #150 +5 others"', () => {
    const line = repostAttribution(
      item({ reposters: [artist('other', 400), artist('festivillainz', 150)], reposter_count: 6 })
    );
    expect(line).toMatchObject({ prefix: 'Reposted by', rankLabel: '#150', othersLabel: '+5 others' });
    expect(line?.artist.slug).toBe('festivillainz');
  });

  it('never reports fewer reposters than were returned', () => {
    const line = repostAttribution(item({ reposters: [artist('a', 1), artist('b', 2)], reposter_count: 0 }));
    expect(line?.othersLabel).toBe('+1 other');
  });

  it('shows the uploader rank only for releases', () => {
    const release = item({ sources: ['release'], uploader: artist('up', 25) });
    expect(uploadAttribution(release)).toMatchObject({ prefix: 'Uploaded by', rankLabel: '#25', othersLabel: null });
    expect(uploadAttribution({ ...release, sources: ['repost'] })).toBeNull();
  });

  it('returns one line per source, upload first', () => {
    const both = item({
      sources: ['release', 'repost'],
      uploader: artist('up', null),
      reposters: [artist('rp', 10)],
      reposter_count: 1,
    });
    const lines = feedAttributions(both);
    expect(lines.map((line) => line.prefix)).toEqual(['Uploaded by', 'Reposted by']);
    expect(lines[0]?.rankLabel).toBeNull();
    expect(lines[1]?.othersLabel).toBeNull();
  });
});

describe('keep score', () => {
  it('labels the probability and flags likely keeps at 70%', () => {
    expect(formatKeepScore(0.354)).toBe('35% keep');
    expect(isLikelyKeep(0.7)).toBe(true);
    expect(isLikelyKeep(0.69)).toBe(false);
  });
});

describe('filter labels', () => {
  it('labels chips with the current value', () => {
    expect(sourceChipLabel('all')).toBe('Source: All');
    expect(sourceChipLabel('reposts')).toBe('Source: Reposts');
    expect(rankChipLabel(undefined)).toBe('Rank: All');
    expect(rankChipLabel(50)).toBe('Rank: Top 50');
  });

  it('keeps the old option testIDs', () => {
    expect(SOURCE_OPTIONS.map((option) => option.testID)).toEqual([
      'feed-source-all',
      'feed-source-releases',
      'feed-source-reposts',
    ]);
    expect(RANK_OPTIONS.map((option) => option.testID)).toEqual([
      'feed-rank-all',
      'feed-rank-25',
      'feed-rank-50',
      'feed-rank-75',
      'feed-rank-100',
      'feed-rank-200',
    ]);
  });

  it('round-trips option keys and rejects unknown ones', () => {
    expect(rankFromKey(rankKey(75))).toBe(75);
    expect(rankFromKey(rankKey(undefined))).toBeUndefined();
    expect(rankFromKey('76')).toBeUndefined();
    expect(sourceFromKey('releases')).toBe('releases');
    expect(sourceFromKey('bogus')).toBe('all');
  });
});
