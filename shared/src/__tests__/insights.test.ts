import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createApiClient, setDefaultApiClient } from '../api/client';
import { formatKeepPct, formatLift, getInsightTracks, getInsights, sortInsightRows, type InsightRow } from '../api/insights';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);

function row(value: string, seen: number, lift: number): InsightRow {
  return { value, seen, lift, keeps: 0, not_quites: 0, nopes: 0, keep_pct: 0 };
}

describe('insights API', () => {
  beforeEach(() => {
    fetchMock.mockReset();
    fetchMock.mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
    setDefaultApiClient(createApiClient('/api'));
  });

  it('requests a dimension with the min count', async () => {
    await getInsights('genre');
    await getInsights('keyword', 3);
    expect(fetchMock.mock.calls[0][0]).toBe('/api/insights?dimension=genre&min_count=8');
    expect(fetchMock.mock.calls[1][0]).toBe('/api/insights?dimension=keyword&min_count=3');
  });

  it('encodes the drill-down value', async () => {
    await getInsightTracks('keyword', 'radio show');
    expect(fetchMock.mock.calls[0][0]).toBe('/api/insights/tracks?dimension=keyword&value=radio+show');
  });
});

describe('insight helpers', () => {
  it('keeps server lift order or sorts by count', () => {
    const rows = [row('a', 9, 20), row('b', 30, -5), row('c', 30, 4)];
    expect(sortInsightRows(rows, 'lift').map((r) => r.value)).toEqual(['a', 'b', 'c']);
    expect(sortInsightRows(rows, 'count').map((r) => r.value)).toEqual(['c', 'b', 'a']);
  });

  it('formats lift and keep %', () => {
    expect(formatLift(12.46)).toBe('+12.5 pts');
    expect(formatLift(-3)).toBe('-3 pts');
    expect(formatLift(0)).toBe('0 pts');
    expect(formatKeepPct(37.5)).toBe('37.5%');
    expect(formatKeepPct(null)).toBe('-');
  });
});
