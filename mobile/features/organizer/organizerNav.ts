/**
 * Pure navigation-state helpers for the organizer stack.
 */

export const SESSION_ROUTE_NAME = '[sessionId]';

/** Minimal shape of a react-navigation state tree (only what we read). */
export interface NavStateLike {
  routes: readonly { key?: string; name: string; state?: NavStateLike }[];
}

/**
 * True when the organizer stack nested under tab route `tabRouteKey` has a
 * session screen open. A stack that hasn't mounted yet has no state: closed.
 */
export function hasOpenSession(tabState: NavStateLike, tabRouteKey: string): boolean {
  const tabRoute = tabState.routes.find((r) => r.key === tabRouteKey);
  return tabRoute?.state?.routes.some((r) => r.name === SESSION_ROUTE_NAME) ?? false;
}
