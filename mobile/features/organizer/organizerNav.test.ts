import { describe, expect, it } from 'vitest';
import { hasOpenSession } from './organizerNav';
import type { NavStateLike } from './organizerNav';

function tabs(organizerState?: NavStateLike): NavStateLike {
  return {
    routes: [
      { key: 'feed-1', name: 'feed' },
      { key: 'org-1', name: 'organizer', state: organizerState },
    ],
  };
}

describe('hasOpenSession', () => {
  it('is false before the organizer stack mounts', () => {
    expect(hasOpenSession(tabs(), 'org-1')).toBe(false);
  });

  it('is false on the picker alone', () => {
    expect(hasOpenSession(tabs({ routes: [{ key: 'i', name: 'index' }] }), 'org-1')).toBe(false);
  });

  it('is true with a session on the stack', () => {
    const state = tabs({ routes: [{ key: 'i', name: 'index' }, { key: 's', name: '[sessionId]' }] });
    expect(hasOpenSession(state, 'org-1')).toBe(true);
  });

  it('is false for an unknown tab key', () => {
    expect(hasOpenSession(tabs({ routes: [{ key: 's', name: '[sessionId]' }] }), 'nope')).toBe(false);
  });
});
