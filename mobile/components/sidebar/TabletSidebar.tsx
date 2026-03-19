/**
 * Tablet sidebar — permanent navigation + pinned playlists.
 * Mirrors web sidebar in simplified form.
 * Only rendered on tablet (≥768dp).
 */
import { View, Text, Pressable, FlatList, StyleSheet } from 'react-native';
import { router, usePathname } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { getPlaylistsByLibrary } from '@music-minion/shared';
import type { Playlist } from '@music-minion/shared';

interface NavItem {
  href: string;
  label: string;
  icon: string;
}

const navItems: NavItem[] = [
  { href: '/(tabs)', label: 'Home', icon: '♫' },
  { href: '/(tabs)/comparison', label: 'Compare', icon: '⚖' },
  { href: '/(tabs)/organizer', label: 'Organize', icon: '☰' },
  { href: '/(tabs)/history', label: 'History', icon: '⏱' },
  { href: '/(tabs)/settings', label: 'Settings', icon: '⚙' },
];

export function TabletSidebar() {
  const pathname = usePathname();

  const { data: playlists } = useQuery({
    queryKey: ['playlists', 'local'],
    queryFn: () => getPlaylistsByLibrary('local'),
    staleTime: 60_000,
  });

  const pinnedPlaylists = playlists
    ?.filter((p: Playlist) => p.pin_order !== null)
    .sort((a: Playlist, b: Playlist) => (a.pin_order ?? 0) - (b.pin_order ?? 0))
    ?? [];

  return (
    <View style={styles.sidebar}>
      {/* App title */}
      <View style={styles.titleArea}>
        <Text style={styles.title}>Music Minion</Text>
      </View>

      {/* Navigation */}
      <View style={styles.navSection}>
        <Text style={styles.sectionLabel}>PAGES</Text>
        {navItems.map((item) => {
          const isActive = pathname === item.href ||
            (item.href === '/(tabs)' && pathname === '/');
          return (
            <Pressable
              key={item.href}
              style={[styles.navItem, isActive && styles.navItemActive]}
              onPress={() => router.push(item.href as never)}
            >
              <Text style={styles.navIcon}>{item.icon}</Text>
              <Text style={[styles.navLabel, isActive && styles.navLabelActive]}>
                {item.label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      {/* Pinned playlists */}
      {pinnedPlaylists.length > 0 && (
        <View style={styles.playlistSection}>
          <Text style={styles.sectionLabel}>PLAYLISTS</Text>
          <FlatList
            data={pinnedPlaylists}
            keyExtractor={(item) => item.id.toString()}
            scrollEnabled={false}
            renderItem={({ item }) => (
              <Pressable style={styles.playlistItem}>
                <Text style={styles.playlistName} numberOfLines={1}>
                  {item.name}
                </Text>
                <Text style={styles.playlistCount}>{item.track_count}</Text>
              </Pressable>
            )}
          />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  sidebar: {
    width: 240,
    backgroundColor: '#1A1A1A',
    borderRightWidth: 1,
    borderRightColor: '#333',
    paddingTop: 48,
  },
  titleArea: {
    paddingHorizontal: 20,
    paddingBottom: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2A2A2A',
  },
  title: {
    color: '#E0E0E0',
    fontSize: 18,
    fontWeight: 'bold',
  },
  navSection: {
    paddingTop: 12,
    paddingHorizontal: 8,
  },
  sectionLabel: {
    color: '#666',
    fontSize: 10,
    letterSpacing: 2,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  navItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 8,
    marginBottom: 2,
  },
  navItemActive: {
    backgroundColor: '#7C4DFF1A',
    borderLeftWidth: 3,
    borderLeftColor: '#7C4DFF',
  },
  navIcon: {
    fontSize: 18,
    width: 24,
    textAlign: 'center',
  },
  navLabel: {
    color: '#9E9E9E',
    fontSize: 14,
  },
  navLabelActive: {
    color: '#7C4DFF',
    fontWeight: '600',
  },
  playlistSection: {
    paddingTop: 12,
    paddingHorizontal: 8,
    borderTopWidth: 1,
    borderTopColor: '#2A2A2A',
    marginTop: 8,
  },
  playlistItem: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 6,
  },
  playlistName: {
    color: '#9E9E9E',
    fontSize: 13,
    flex: 1,
    marginRight: 8,
  },
  playlistCount: {
    color: '#666',
    fontSize: 11,
    fontFamily: 'monospace',
  },
});
