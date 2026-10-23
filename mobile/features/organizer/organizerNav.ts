/**
 * Pure navigation-state helpers for the organizer stack.
 */

export const SESSION_ROUTE_NAME = '[sessionId]';

/** Drawer route name of the organizer stack (the `organizer/` directory). */
export const ORGANIZER_ROUTE_NAME = 'organizer';

/** Minimal shape of a react-navigation state tree (only what we read). */
export interface NavStateLike {
  routes: readonly { key?: string; name: string; state?: NavStateLike }[];
}

/**
 * True when the organizer stack nested under the drawer has a session screen
 * open. A stack that hasn't mounted yet has no state: closed.
 */
export function hasOpenSession(drawerState: NavStateLike): boolean {
  const organizer = drawerState.routes.find((r) => r.name === ORGANIZER_ROUTE_NAME);
  return organizer?.state?.routes.some((r) => r.name === SESSION_ROUTE_NAME) ?? false;
}
