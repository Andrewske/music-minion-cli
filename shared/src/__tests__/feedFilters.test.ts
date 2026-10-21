import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createApiClient, setDefaultApiClient } from '../api/client';
import {
  criterionChanges,
  flagFeedItem,
  formatPrecision,
  getFlaggedTracks,
  ruleCriterion,
  unflagFeedItem,
  updateFilterRule,
} from '../api/feedFilters';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

describe('feed filter API', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({ ok: true, json: () => Promise.resolve({ items: [], next_cursor: null }) });
    setDefaultApiClient(createApiClient('/api'));
  });

  it('flags with a reason and only sends a non-blank note', async () => {
    await flagFeedItem('42', 'podcast', '  ');
    await flagFeedItem('42', 'live_mix', 'boiler room');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/feed/42/flag');
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ reason: 'podcast' });
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ reason: 'live_mix', note: 'boiler room' });
  });

  it('un-flags with DELETE', async () => {
    await unflagFeedItem('42');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/feed/42/flag');
    expect(fetchMock.mock.calls[0][1].method).toBe('DELETE');
  });

  it('lists filtered tracks by default and passes rule and cursor', async () => {
    await getFlaggedTracks();
    await getFlaggedTracks({ source: 'user', ruleId: 3, cursor: 99 });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/feed-filters/tracks?limit=50&source=filtered');
    expect(fetchMock.mock.calls[1][0]).toBe('/api/feed-filters/tracks?limit=50&source=user&rule_id=3&cursor=99');
  });

  it('patches rules', async () => {
    await updateFilterRule(5, { enabled: false });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/feed-filters/rules/5');
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'PATCH', body: '{"enabled":false}' });
  });
});

describe('rule helpers', () => {
  it('formats precision', () => {
    expect(formatPrecision(null)).toBe('-');
    expect(formatPrecision(0.916)).toBe('92%');
  });

  it('maps a single criterion field to the rule kind', () => {
    expect(ruleCriterion({ kind: 'duration_min', pattern: null, threshold: 15 })).toBe('15');
    expect(ruleCriterion({ kind: 'title_regex', pattern: 'b2b', threshold: null })).toBe('b2b');
    expect(criterionChanges('duration_min', '20')).toEqual({ threshold: 20 });
    expect(criterionChanges('tag_match', 'podcast')).toEqual({ pattern: 'podcast' });
  });
});
