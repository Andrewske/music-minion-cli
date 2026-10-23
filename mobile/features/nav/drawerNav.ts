/**
 * Pure drawer-navigation model: which destinations exist, how they group,
 * and what tapping one should do given the current drawer state.
 */
import { ORGANIZER_ROUTE_NAME, hasOpenSession } from '../organizer/organizerNav';
import type { NavStateLike } from '../organizer/organizerNav';

export type NavKey = 'home' | 'feed' | 'compare' | 'organize' | 'history' | 'settings';

export interface NavItem {
  key: NavKey;
  label: string;
  /** Drawer route name (file/dir name under `app/(main)`). */
  routeName: string;
  /** URL path. The `(main)` group is invisible in URLs. */
  href: string;
}

const ITEMS: Record<NavKey, NavItem> = {
  home: { key: 'home', label: 'Home', routeName: 'index', href: '/' },
  feed: { key: 'feed', label: 'Feed', routeName: 'feed', href: '/feed' },
  compare: { key: 'compare', label: 'Compare', routeName: 'comparison', href: '/comparison' },
  organize: { key: 'organize', label: 'Organize', routeName: ORGANIZER_ROUTE_NAME, href: '/organizer' },
  history: { key: 'history', label: 'History', routeName: 'history', href: '/history' },
  settings: { key: 'settings', label: 'Settings', routeName: 'settings', href: '/settings' },
};

/** Drawer groups, top to bottom. A divider sits before the last group. */
export const NAV_GROUPS: readonly (readonly NavItem[])[] = [
  [ITEMS.home, ITEMS.feed],
  [ITEMS.compare, ITEMS.organize],
  [ITEMS.history, ITEMS.settings],
];

/** Maestro / accessibility testID for a drawer row. */
export function navTestId(key: NavKey): string {
  return `nav-${key}`;
}

/** Nav item for a drawer route name, or undefined for routes not in the drawer. */
export function navItemForRoute(routeName: string): NavItem | undefined {
  return Object.values(ITEMS).find((item) => item.routeName === routeName);
}

export type NavIntent =
  | { kind: 'close' }
  | { kind: 'navigate'; routeName: string }
  | { kind: 'reset-organizer'; href: string };

/**
 * What a drawer tap should do. Organize with a session open always returns
 * to the picker (the picker offers Resume); tapping the current screen just
 * closes the drawer; anything else navigates.
 */
export function resolveNavIntent(item: NavItem, drawerState: NavStateLike, activeRouteName: string): NavIntent {
  if (item.key === 'organize' && hasOpenSession(drawerState)) {
    return { kind: 'reset-organizer', href: item.href };
  }
  if (item.routeName === activeRouteName) return { kind: 'close' };
  return { kind: 'navigate', routeName: item.routeName };
}
