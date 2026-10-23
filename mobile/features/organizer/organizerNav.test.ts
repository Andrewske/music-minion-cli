import { describe, expect, it } from 'vitest';
import { hasOpenSession } from './organizerNav';
import type { NavStateLike } from './organizerNav';

function drawer(organizerState?: NavStateLike): NavStateLike {
  return {
    routes: [
      { key: 'index-1', name: 'index' },
      { key: 'feed-1', name: 'feed' },
      { key: 'org-1', name: 'organizer', state: organizerState },
    ],
  };
}

describe('hasOpenSession', () => {
  it('is false before the organizer stack mounts', () => {
    expect(hasOpenSession(drawer())).toBe(false);
  });

  it('is false on the picker alone', () => {
    expect(hasOpenSession(drawer({ routes: [{ key: 'i', name: 'index' }] }))).toBe(false);
  });

  it('is true with a session on the stack', () => {
    const state = drawer({ routes: [{ key: 'i', name: 'index' }, { key: 's', name: '[sessionId]' }] });
    expect(hasOpenSession(state)).toBe(true);
  });

  it('is false when the drawer has no organizer route', () => {
    expect(hasOpenSession({ routes: [{ key: 'f', name: 'feed' }] })).toBe(false);
  });
});
