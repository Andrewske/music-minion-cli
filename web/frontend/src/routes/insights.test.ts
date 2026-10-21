import { describe, expect, it, vi } from 'vitest';
import { Route, type InsightsSearch } from './insights';

vi.mock('../components/insights/InsightsPage', () => ({ InsightsPage: () => null }));

const validate = (search: Record<string, unknown>): InsightsSearch =>
  (Route.options.validateSearch as (s: Record<string, unknown>) => InsightsSearch)(search);

describe('/insights search params', () => {
  it('restores tab, min count and sort', () => {
    expect(validate({ tab: 'reposters', minCount: '3', sort: 'count' })).toEqual({ tab: 'reposters', minCount: 3, sort: 'count' });
  });

  it('omits defaults and drops invalid values', () => {
    expect(validate({ tab: 'keywords', minCount: '8', sort: 'lift' })).toEqual({ tab: undefined, minCount: undefined, sort: undefined });
    expect(validate({ tab: 'nope', minCount: '-1' })).toEqual({ tab: undefined, minCount: undefined, sort: undefined });
  });
});
