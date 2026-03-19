/**
 * Tab layout — adaptive: bottom tabs on phone, sidebar on tablet.
 *
 * Phone (< 768dp):     Bottom tab bar
 * Tablet (≥ 768dp):    Permanent sidebar + content area (tabs hidden)
 */
import { View, Text } from 'react-native';
import { Tabs, Slot } from 'expo-router';
import { useAdaptiveLayout } from '../../hooks/useAdaptiveLayout';
import { TabletSidebar } from '../../components/sidebar/TabletSidebar';

export default function TabLayout() {
  const { isTablet } = useAdaptiveLayout();

  // Tablet: sidebar + slot (no bottom tabs)
  if (isTablet) {
    return (
      <View style={{ flex: 1, flexDirection: 'row', backgroundColor: '#121212' }}>
        <TabletSidebar />
        <View style={{ flex: 1 }}>
          <Slot />
        </View>
      </View>
    );
  }

  // Phone: bottom tabs
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: '#1E1E1E',
          borderTopColor: '#333',
          height: 56,
          paddingBottom: 8,
          paddingTop: 8,
        },
        tabBarActiveTintColor: '#7C4DFF',
        tabBarInactiveTintColor: '#9E9E9E',
        tabBarLabelStyle: {
          fontSize: 12,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Home',
          tabBarIcon: ({ color }) => <TabIcon name="♫" color={color} />,
        }}
      />
      <Tabs.Screen
        name="comparison"
        options={{
          title: 'Compare',
          tabBarIcon: ({ color }) => <TabIcon name="⚖" color={color} />,
        }}
      />
      <Tabs.Screen
        name="organizer"
        options={{
          title: 'Organize',
          tabBarIcon: ({ color }) => <TabIcon name="☰" color={color} />,
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: 'History',
          tabBarIcon: ({ color }) => <TabIcon name="⏱" color={color} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Settings',
          tabBarIcon: ({ color }) => <TabIcon name="⚙" color={color} />,
        }}
      />
    </Tabs>
  );
}

function TabIcon({ name, color }: { name: string; color: string }) {
  return (
    <View style={{ alignItems: 'center', justifyContent: 'center' }}>
      <Text style={{ color, fontSize: 20 }}>{name}</Text>
    </View>
  );
}
