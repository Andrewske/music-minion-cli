import { describe, expect, it } from 'vitest';
import type { InsightRow } from '../../api/insights';
import { liftBar, maxAbsLift, parseMinCount, tabByKey } from './insightsView';

const row = (lift: number): InsightRow => ({ value: String(lift), seen: 10, keeps: 0, not_quites: 0, nopes: 0, keep_pct: 0, lift });

describe('insights view helpers', () => {
  it('scales lift bars to the largest |lift| in the table', () => {
    const maxAbs = maxAbsLift([row(10), row(-20), row(5)]);
    expect(maxAbs).toBe(20);
    expect(liftBar(10, maxAbs)).toEqual({ side: 'up', widthPct: 50 });
    expect(liftBar(-20, maxAbs)).toEqual({ side: 'down', widthPct: 100 });
    expect(liftBar(0, maxAbs)).toEqual({ side: 'none', widthPct: 0 });
    expect(liftBar(3, 0)).toEqual({ side: 'none', widthPct: 0 });
  });

  it('falls back to the first tab', () => {
    expect(tabByKey('other').dimensions).toEqual(['duration', 'age']);
    expect(tabByKey('bogus').key).toBe('keywords');
    expect(tabByKey(undefined).key).toBe('keywords');
  });

  it('accepts only whole min counts in range', () => {
    expect(parseMinCount('3')).toBe(3);
    expect(parseMinCount('0')).toBeUndefined();
    expect(parseMinCount('2.5')).toBeUndefined();
    expect(parseMinCount('abc')).toBeUndefined();
    expect(parseMinCount(5000)).toBeUndefined();
  });
});
