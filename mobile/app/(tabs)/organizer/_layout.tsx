import { useEffect } from 'react';
import { Stack, router, useNavigation } from 'expo-router';
import type { BottomTabNavigationProp } from '@react-navigation/bottom-tabs';
import type { ParamListBase } from '@react-navigation/native';
import { hasOpenSession } from '../../../features/organizer/organizerNav';

/** Single id for every session screen, so opening a session never stacks on another. */
const SESSION_SCREEN_ID = 'organizer-session';

export default function OrganizerLayout(): React.JSX.Element {
  // The layout renders as the Organize tab's screen, so this is the tab
  // navigator's handle for our route. Pressing the Organize tab button with a
  // session open returns to the picker (which offers "Resume"). Plain focus
  // changes (e.g. back from an artist page) leave the session alone.
  const navigation = useNavigation<BottomTabNavigationProp<ParamListBase>>();

  useEffect(() => {
    return navigation.addListener('tabPress', (e) => {
      if (!hasOpenSession(navigation.getState(), e.target ?? '')) return;
      router.dismissTo('/(tabs)/organizer');
    });
  }, [navigation]);

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="index" />
      <Stack.Screen name="[sessionId]" getId={() => SESSION_SCREEN_ID} />
    </Stack>
  );
}
