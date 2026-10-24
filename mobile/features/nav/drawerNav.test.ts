import { describe, expect, it } from 'vitest';
import { NAV_GROUPS, navItemForRoute, navTestId, resolveNavIntent } from './drawerNav';
import type { NavItem, NavKey } from './drawerNav';
import type { NavStateLike } from '../organizer/organizerNav';

function item(key: NavKey): NavItem {
  const found = NAV_GROUPS.flat().find((i) => i.key === key);
  if (!found) throw new Error(`no nav item ${key}`);
  return found;
}

const withSession: NavStateLike = {
  routes: [
    { key: 'h', name: 'index' },
    { key: 'o', name: 'organizer', state: { routes: [{ name: 'index' }, { name: '[sessionId]' }] } },
  ],
};
const noSession: NavStateLike = { routes: [{ key: 'h', name: 'index' }, { key: 'o', name: 'organizer' }] };

describe('NAV_GROUPS', () => {
  it('lists the six destinations in drawer order', () => {
    const keys = NAV_GROUPS.flat().map((i) => i.key);
    expect(keys).toEqual(['home', 'feed', 'compare', 'organize', 'history', 'settings']);
  });

  it('uses group-free URLs', () => {
    expect(NAV_GROUPS.flat().every((i) => !i.href.includes('('))).toBe(true);
  });
});

describe('navTestId / navItemForRoute', () => {
  it('builds nav-* testIDs', () => {
    expect(navTestId('organize')).toBe('nav-organize');
  });

  it('maps route names to items', () => {
    expect(navItemForRoute('index')?.key).toBe('home');
    expect(navItemForRoute('comparison')?.key).toBe('compare');
    expect(navItemForRoute('artist/[id]')).toBeUndefined();
  });
});

describe('resolveNavIntent', () => {
  it('resets the organizer when a session is open, even from another screen', () => {
    expect(resolveNavIntent(item('organize'), withSession, 'index')).toEqual({ kind: 'reset-organizer', href: '/organizer' });
    expect(resolveNavIntent(item('organize'), withSession, 'organizer').kind).toBe('reset-organizer');
  });

  it('closes when tapping the active screen', () => {
    expect(resolveNavIntent(item('organize'), noSession, 'organizer')).toEqual({ kind: 'close' });
    expect(resolveNavIntent(item('home'), noSession, 'index')).toEqual({ kind: 'close' });
  });

  it('navigates to other screens', () => {
    expect(resolveNavIntent(item('feed'), withSession, 'index')).toEqual({ kind: 'navigate', routeName: 'feed' });
  });
});
