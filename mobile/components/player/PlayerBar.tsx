/**
 * Persistent player bar — collapsed at bottom of screen.
 *
 * Collapsed: track title + artist, play/pause, skip
 * Tap to expand → NowPlaying bottom sheet (Phase 4 v2)
 *
 * Phone: fixed bottom bar, full width
 * Tablet: same for now (sidebar footer in Phase 5)
 */
import { View, Text, Pressable, StyleSheet } from 'react-native';
import * as Haptics from 'expo-haptics';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { usePlayer } from '../../hooks/usePlayer';

export function PlayerBar() {
  const insets = useSafeAreaInsets();
  const {
    currentTrack,
    isPlaying,
    isThisDeviceActive,
    pause,
    resume,
    next,
    prev,
  } = usePlayer();

  if (!currentTrack) {
    return (
      <View style={[styles.barEmpty, { paddingBottom: 10 + insets.bottom }]}>
        <Text style={styles.emptyText}>Nothing playing</Text>
      </View>
    );
  }

  const handlePlayPause = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    if (isPlaying) {
      pause();
    } else {
      resume();
    }
  };

  const handlePrev = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    prev();
  };

  const handleNext = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    next();
  };

  return (
    <View style={[styles.bar, { paddingBottom: 10 + insets.bottom }]}>
      {/* Track info */}
      <View style={styles.info}>
        <Text style={styles.title} numberOfLines={1}>
          {currentTrack.title}
        </Text>
        <Text style={styles.artist} numberOfLines={1}>
          {currentTrack.artist ?? 'Unknown Artist'}
          {!isThisDeviceActive && ' · Playing elsewhere'}
        </Text>
      </View>

      {/* Controls */}
      <View style={styles.controls}>
        <Pressable style={styles.controlBtn} onPress={handlePrev} hitSlop={8}>
          <Text style={styles.controlIcon}>⏮</Text>
        </Pressable>

        <Pressable
          style={[styles.controlBtn, styles.playBtn]}
          onPress={handlePlayPause}
          hitSlop={8}
        >
          <Text style={styles.playIcon}>
            {isPlaying ? '⏸' : '▶'}
          </Text>
        </Pressable>

        <Pressable style={styles.controlBtn} onPress={handleNext} hitSlop={8}>
          <Text style={styles.controlIcon}>⏭</Text>
        </Pressable>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#1A1A1A',
    borderTopWidth: 1,
    borderTopColor: '#333',
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 10,
  },
  barEmpty: {
    backgroundColor: '#1A1A1A',
    borderTopWidth: 1,
    borderTopColor: '#333',
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 10,
    justifyContent: 'center',
  },
  emptyText: {
    color: '#555',
    fontSize: 13,
  },
  info: {
    flex: 1,
    marginRight: 12,
  },
  title: {
    color: '#E0E0E0',
    fontSize: 14,
    fontWeight: '600',
  },
  artist: {
    color: '#9E9E9E',
    fontSize: 12,
    marginTop: 1,
  },
  controls: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  controlBtn: {
    width: 40,
    height: 40,
    alignItems: 'center',
    justifyContent: 'center',
  },
  playBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#7C4DFF',
  },
  controlIcon: {
    fontSize: 18,
    color: '#E0E0E0',
  },
  playIcon: {
    fontSize: 18,
    color: '#fff',
  },
});
