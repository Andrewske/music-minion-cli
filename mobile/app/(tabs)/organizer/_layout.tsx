import { useCallback } from 'react';
import { Stack, router, useFocusEffect } from 'expo-router';

/** Single id for every session screen, so opening a session never stacks on another. */
const SESSION_SCREEN_ID = 'organizer-session';

export default function OrganizerLayout(): React.JSX.Element {
  // Coming back to Organize lands on the picker (it offers "Resume").
  useFocusEffect(
    useCallback((): void => {
      if (router.canDismiss()) router.dismissAll();
    }, [])
  );

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="index" />
      <Stack.Screen name="[sessionId]" getId={() => SESSION_SCREEN_ID} />
    </Stack>
  );
}
