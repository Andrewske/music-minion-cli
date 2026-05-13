/**
 * Expanded Now Playing view — full-screen bottom sheet.
 *
 * Shows: album art placeholder, track title/artist, seek slider,
 * prev/play/next controls (56dp), shuffle toggle, queue info.
 */
import { View, Text, Pressable, StyleSheet, ScrollView } from 'react-native';
import * as Haptics from 'expo-haptics';
import TrackPlayer from '@rntp/player';
import { usePlayer } from '../../hooks/usePlayer';
import { SeekSlider } from './SeekSlider';

interface NowPlayingProps {
  onCollapse: () => void;
}

export function NowPlaying({ onCollapse }: NowPlayingProps) {
  const {
    currentTrack,
    isPlaying,
    shuffleEnabled,
    queue,
    queueIndex,
    pause,
    resume,
    next,
    prev,
    seek,
    toggleShuffleSmooth,
    rntpPosition,
  } = usePlayer();

  if (!currentTrack) return null;

  const handlePlayPause = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    if (isPlaying) pause();
    else resume();
  };

  const handlePrev = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    prev();
  };

  const handleNext = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    next();
  };

  const handleSeek = (seconds: number) => {
    seek(seconds * 1000);
    TrackPlayer.seekTo(seconds);
  };

  const handleShuffle = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    toggleShuffleSmooth();
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Drag handle */}
      <Pressable style={styles.handleArea} onPress={onCollapse}>
        <View style={styles.handle} />
      </Pressable>

      {/* Album art placeholder */}
      <View style={styles.artContainer}>
        <View style={styles.art}>
          <Text style={styles.artEmoji}>
            {currentTrack.emojis?.[0] ?? '♪'}
          </Text>
        </View>
      </View>

      {/* Track info */}
      <Text style={styles.title} numberOfLines={2}>
        {currentTrack.title}
      </Text>
      <Text style={styles.artist} numberOfLines={1}>
        {currentTrack.artist ?? 'Unknown Artist'}
      </Text>

      {/* Seek slider */}
      <SeekSlider
        position={rntpPosition}
        duration={currentTrack.duration ?? 0}
        onSeek={handleSeek}
      />

      {/* Main controls */}
      <View style={styles.mainControls}>
        <Pressable style={styles.mainBtn} onPress={handlePrev}>
          <Text style={styles.mainBtnText}>⏮</Text>
        </Pressable>

        <Pressable
          style={[styles.mainBtn, styles.playMainBtn]}
          onPress={handlePlayPause}
        >
          <Text style={styles.playMainText}>
            {isPlaying ? '⏸' : '▶'}
          </Text>
        </Pressable>

        <Pressable style={styles.mainBtn} onPress={handleNext}>
          <Text style={styles.mainBtnText}>⏭</Text>
        </Pressable>
      </View>

      {/* Secondary controls */}
      <View style={styles.secondaryControls}>
        <Pressable
          style={[styles.toggleBtn, shuffleEnabled && styles.toggleActive]}
          onPress={handleShuffle}
        >
          <Text style={[styles.toggleText, shuffleEnabled && styles.toggleTextActive]}>
            🔀 Shuffle
          </Text>
        </Pressable>

        <Text style={styles.queueInfo}>
          {queueIndex + 1} / {queue.length} in queue
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#121212',
  },
  content: {
    alignItems: 'center',
    paddingBottom: 40,
  },
  handleArea: {
    width: '100%',
    alignItems: 'center',
    paddingVertical: 12,
  },
  handle: {
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#555',
  },
  artContainer: {
    marginTop: 24,
    marginBottom: 24,
  },
  art: {
    width: 200,
    height: 200,
    borderRadius: 16,
    backgroundColor: '#1E1E1E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  artEmoji: {
    fontSize: 72,
  },
  title: {
    color: '#E0E0E0',
    fontSize: 22,
    fontWeight: 'bold',
    textAlign: 'center',
    paddingHorizontal: 32,
    marginBottom: 4,
  },
  artist: {
    color: '#9E9E9E',
    fontSize: 16,
    textAlign: 'center',
    marginBottom: 24,
  },
  mainControls: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 24,
    marginTop: 16,
    marginBottom: 24,
  },
  mainBtn: {
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: 'center',
    justifyContent: 'center',
  },
  playMainBtn: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: '#7C4DFF',
  },
  mainBtnText: {
    fontSize: 28,
    color: '#E0E0E0',
  },
  playMainText: {
    fontSize: 28,
    color: '#fff',
  },
  secondaryControls: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: '100%',
    paddingHorizontal: 32,
  },
  toggleBtn: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#2A2A2A',
  },
  toggleActive: {
    backgroundColor: '#7C4DFF33',
  },
  toggleText: {
    color: '#9E9E9E',
    fontSize: 13,
  },
  toggleTextActive: {
    color: '#7C4DFF',
  },
  queueInfo: {
    color: '#666',
    fontSize: 12,
    fontFamily: 'monospace',
  },
});
