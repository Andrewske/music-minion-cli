import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createApiClient, setDefaultApiClient } from '../api/client';
import {
  acceptRuleSuggestion,
  classifyAmbiguousTracks,
  describeClassifyResult,
  resolveClassification,
} from '../api/feedAgent';
import { formatConfidence, getFlaggedTracks } from '../api/feedFilters';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

describe('feed agent API', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({ ok: true, json: () => Promise.resolve({ items: [] }) });
    setDefaultApiClient(createApiClient('/api'));
  });

  it('classifies with an optional cap', async () => {
    await classifyAmbiguousTracks();
    await classifyAmbiguousTracks(20);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/feed-filters/classify');
    expect(fetchMock.mock.calls[0][1].body).toBeUndefined();
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ max_tracks: 20 });
  });

  it('confirms or dismisses a classification', async () => {
    await resolveClassification(4, true);
    await resolveClassification(4, false);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/feed-filters/classifications/4/confirm');
    expect(fetchMock.mock.calls[1][0]).toBe('/api/feed-filters/classifications/4/dismiss');
  });

  it('accepts a suggestion with overrides', async () => {
    await acceptRuleSuggestion(7, { pattern: 'radio' });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/feed-filters/suggestions/7/accept');
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ pattern: 'radio' });
  });

  it('pages flagged tracks by confidence', async () => {
    await getFlaggedTracks({ source: 'agent', sort: 'confidence', cursor: 5, cursorConfidence: 0.9 });
    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/feed-filters/tracks?limit=50&source=agent&cursor=5&sort=confidence&cursor_confidence=0.9'
    );
  });
});

describe('feed agent helpers', () => {
  it('summarizes a run', () => {
    const base = { candidates: 12, classified: 12, auto_flagged: 2, pending: 3, invalid: 0, failed_batches: 0 };
    expect(describeClassifyResult(base)).toBe('Checked 12 of 12: 2 filtered, 3 to review');
    expect(describeClassifyResult({ ...base, failed_batches: 1, classified: 2 })).toContain('(1 batch failed)');
    expect(describeClassifyResult({ ...base, candidates: 0 })).toBe('No ambiguous tracks to check');
    expect(describeClassifyResult({ ...base, invalid: 2 })).toContain('(2 unreadable answers)');
  });

  it('formats confidence only for agent flags', () => {
    expect(formatConfidence(0.873)).toBe('87%');
    expect(formatConfidence(null)).toBeNull();
  });
});
