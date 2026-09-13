import { describe, expect, it, vi } from 'vitest';
import { Route, type FeedSearch } from './feed';

vi.mock('../components/feed/FeedPage', () => ({ FeedPage: () => null }));

const validate = (search: Record<string, unknown>) =>
  (Route.options.validateSearch as (s: Record<string, unknown>) => FeedSearch)(search);

describe('/feed search params', () => {
  it('restores source, rank preset, and toggles from the URL', () => {
    expect(validate({ source: 'reposts', maxRank: '75', inLibrary: 'true', showHidden: true })).toEqual({
      source: 'reposts',
      maxRank: 75,
      inLibrary: true,
      showHidden: true,
    });
  });

  it('drops invalid values and omits the defaults from the URL', () => {
    expect(validate({ source: 'bogus', maxRank: '76', inLibrary: 'no' })).toEqual({
      source: undefined,
      maxRank: undefined,
      inLibrary: undefined,
      showHidden: undefined,
    });
    expect(validate({ source: 'all' }).source).toBeUndefined();
  });

  it('maps the legacy top200 flag onto the Top 200 preset', () => {
    expect(validate({ top200: 'true' }).maxRank).toBe(200);
    expect(validate({ top200: 'true', maxRank: '25' }).maxRank).toBe(25);
  });
});
