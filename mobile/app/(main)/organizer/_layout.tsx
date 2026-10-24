import type { ReactElement } from 'react';
import { Stack } from 'expo-router';

/** Single id for every session screen, so opening a session never stacks on another. */
const SESSION_SCREEN_ID = 'organizer-session';

/**
 * Organizer stack: picker → session. The drawer's Organize item returns to
 * the picker when a session is open (see features/nav/drawerNav.ts).
 */
export default function OrganizerLayout(): ReactElement {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="index" />
      <Stack.Screen name="[sessionId]" getId={() => SESSION_SCREEN_ID} />
    </Stack>
  );
}
