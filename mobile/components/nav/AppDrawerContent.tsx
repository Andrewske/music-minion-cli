/**
 * Drawer content: destinations pinned to the bottom of the drawer so they sit
 * under the thumb on a tall phone. Groups: Home/Feed, Compare/Organize, then
 * a divider and History/Settings. Settings carries the connection dot.
 */
import { Fragment, type ReactElement } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { router } from 'expo-router';
import { CommonActions } from '@react-navigation/native';
import type { DrawerContentComponentProps } from '@react-navigation/drawer';
import { Clock, House, Layers, Rss, Settings, Trophy } from 'lucide-react-native';
import type { LucideIcon } from 'lucide-react-native';
import { NAV_GROUPS, navTestId, resolveNavIntent } from '../../features/nav/drawerNav';
import type { NavIntent, NavItem, NavKey } from '../../features/nav/drawerNav';
import { CONNECTION_DOT_COLORS, connectionLabel } from '../../features/nav/connectionDot';
import { useConnectionStatus } from '../../hooks/useConnectionStatus';

const ICONS: Record<NavKey, LucideIcon> = {
  home: House,
  feed: Rss,
  compare: Trophy,
  organize: Layers,
  history: Clock,
  settings: Settings,
};

type DrawerNavigation = DrawerContentComponentProps['navigation'];

/** Carry out a resolved drawer tap. Navigating closes the drawer by itself. */
function runNavIntent(intent: NavIntent, navigation: DrawerNavigation, drawerKey: string): void {
  if (intent.kind === 'navigate') {
    navigation.dispatch({ ...CommonActions.navigate(intent.routeName), target: drawerKey });
    return;
  }
  // Organize with a session open: pop the organizer stack back to the picker.
  if (intent.kind === 'reset-organizer') router.dismissTo(intent.href);
  navigation.closeDrawer();
}

export function AppDrawerContent({ state, navigation }: DrawerContentComponentProps): ReactElement {
  const activeRouteName = state.routes[state.index]?.name ?? '';
  const handlePress = (item: NavItem): void =>
    runNavIntent(resolveNavIntent(item, state, activeRouteName), navigation, state.key);

  return (
    <View style={styles.container}>
      <Text style={styles.wordmark}>Music Minion</Text>
      <View style={styles.items}>
        {NAV_GROUPS.map((group, i) => (
          <Fragment key={group[0]?.key ?? i}>
            <GroupSpacer index={i} />
            {group.map((item) => (
              <DrawerRow key={item.key} item={item} active={item.routeName === activeRouteName} onPress={handlePress} />
            ))}
          </Fragment>
        ))}
      </View>
    </View>
  );
}

/** Nothing above the first group, a gap between groups, a divider before the last. */
function GroupSpacer({ index }: { index: number }): ReactElement | null {
  if (index === 0) return null;
  return <View style={index === NAV_GROUPS.length - 1 ? styles.divider : styles.gap} />;
}

interface DrawerRowProps {
  item: NavItem;
  active: boolean;
  onPress: (item: NavItem) => void;
}

function DrawerRow({ item, active, onPress }: DrawerRowProps): ReactElement {
  const { status } = useConnectionStatus();
  const Icon = ICONS[item.key];
  const showDot = item.key === 'settings';
  return (
    <Pressable
      testID={navTestId(item.key)}
      accessibilityRole="button"
      accessibilityState={{ selected: active }}
      accessibilityLabel={showDot ? connectionLabel(item.label, status) : item.label}
      onPress={() => onPress(item)}
      android_ripple={{ color: '#FFFFFF14' }}
      // Static style: NativeWind's Pressable wrapper drops function styles.
      style={[styles.row, active && styles.rowActive]}
    >
      <Icon size={22} color={active ? ACTIVE_TINT : '#8A8A8A'} strokeWidth={active ? 2.25 : 2} />
      <Text style={[styles.label, active && styles.labelActive]}>{item.label}</Text>
      {showDot ? <View testID="nav-connection-dot" style={[styles.dot, { backgroundColor: CONNECTION_DOT_COLORS[status] }]} /> : null}
    </Pressable>
  );
}

/** Lighter than the #7C4DFF accent so text on the tinted row stays readable. */
const ACTIVE_TINT = '#B9A3FF';

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#1A1A1A',
    paddingTop: 20,
    paddingBottom: 16,
  },
  wordmark: {
    color: '#5E5E5E',
    fontSize: 14,
    fontWeight: '600',
    paddingHorizontal: 28,
  },
  items: {
    flex: 1,
    justifyContent: 'flex-end',
    paddingHorizontal: 12,
  },
  gap: {
    height: 12,
  },
  divider: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: '#333333',
    marginVertical: 12,
    marginHorizontal: 16,
  },
  row: {
    height: 52,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    paddingHorizontal: 16,
    borderRadius: 14,
    overflow: 'hidden',
  },
  rowActive: {
    backgroundColor: '#7C4DFF29',
  },
  label: {
    flex: 1,
    color: '#C8C8C8',
    fontSize: 16,
    fontWeight: '500',
  },
  labelActive: {
    color: ACTIVE_TINT,
    fontWeight: '600',
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
});
