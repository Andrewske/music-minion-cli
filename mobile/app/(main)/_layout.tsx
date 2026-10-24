/**
 * Main layout: a left drawer holds navigation (no tab bar).
 *
 * Phone (< 768dp):  'front' drawer over the screen with a scrim, opened from
 *                   the ScreenHeader ≡ button only. Edge swipe is off because
 *                   Android's back gesture owns both edges.
 * Tablet (≥ 768dp): 'permanent' drawer with the same content.
 */
import type { ReactElement } from 'react';
import { Drawer } from 'expo-router/drawer';
import type { DrawerContentComponentProps } from '@react-navigation/drawer';
import { useAdaptiveLayout } from '../../hooks/useAdaptiveLayout';
import { AppDrawerContent } from '../../components/nav/AppDrawerContent';

const renderDrawerContent = (props: DrawerContentComponentProps): ReactElement => <AppDrawerContent {...props} />;

export default function MainLayout(): ReactElement {
  const { isTablet } = useAdaptiveLayout();
  return (
    <Drawer
      drawerContent={renderDrawerContent}
      screenOptions={{
        headerShown: false,
        drawerType: isTablet ? 'permanent' : 'front',
        swipeEnabled: false,
        overlayColor: '#000000A6',
        overlayAccessibilityLabel: 'Close menu',
        drawerStyle: {
          width: isTablet ? 248 : 296,
          backgroundColor: '#1A1A1A',
          borderRightWidth: isTablet ? 1 : 0,
          borderRightColor: '#2A2A2A',
        },
        sceneStyle: { backgroundColor: '#121212' },
      }}
    >
      <Drawer.Screen name="index" options={{ title: 'Home' }} />
      <Drawer.Screen name="feed" options={{ title: 'Feed' }} />
      <Drawer.Screen name="comparison" options={{ title: 'Compare' }} />
      <Drawer.Screen name="organizer" options={{ title: 'Organize' }} />
      <Drawer.Screen name="history" options={{ title: 'History' }} />
      <Drawer.Screen name="settings" options={{ title: 'Settings' }} />
    </Drawer>
  );
}
