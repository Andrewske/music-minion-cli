import { describe, expect, it, vi } from 'vitest';
import { Route, type ArtistsSearch } from './artists';

vi.mock('../components/follow-suggestions/SuggestionsView', () => ({ SuggestionsView: () => null }));
vi.mock('../components/unfollow-suggestions/UnfollowView', () => ({ UnfollowView: () => null }));

const validate = (search: Record<string, unknown>): ArtistsSearch =>
  (Route.options.validateSearch as (s: Record<string, unknown>) => ArtistsSearch)(search);

describe('/artists search params', () => {
  it('restores the suggestions and unfollow tabs and omits the default', () => {
    expect(validate({ tab: 'suggestions' })).toEqual({ tab: 'suggestions' });
    expect(validate({ tab: 'unfollow' })).toEqual({ tab: 'unfollow' });
    expect(validate({ tab: 'following' })).toEqual({ tab: undefined });
    expect(validate({ tab: 'bogus' })).toEqual({ tab: undefined });
  });
});
