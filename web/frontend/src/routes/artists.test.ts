import { describe, expect, it, vi } from 'vitest';
import { Route, type ArtistsSearch } from './artists';

vi.mock('../components/follow-suggestions/SuggestionsView', () => ({ SuggestionsView: () => null }));

const validate = (search: Record<string, unknown>): ArtistsSearch =>
  (Route.options.validateSearch as (s: Record<string, unknown>) => ArtistsSearch)(search);

describe('/artists search params', () => {
  it('restores the suggestions tab and omits the default', () => {
    expect(validate({ tab: 'suggestions' })).toEqual({ tab: 'suggestions' });
    expect(validate({ tab: 'following' })).toEqual({ tab: undefined });
    expect(validate({ tab: 'bogus' })).toEqual({ tab: undefined });
  });
});
