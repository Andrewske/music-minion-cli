/**
 * Track card — title, artist, rating, duration.
 * Tap to play, long-press for quick actions (love/unlove, add to bucket).
 */
import { View, Text, Pressable, StyleSheet } from 'react-native';
import * as Haptics from 'expo-haptics';
import type { Track } from '@music-minion/shared';

interface TrackCardProps {
  track: Track;
  isPlaying?: boolean;
  onPress: () => void;
  onLongPress?: () => void;
  testID?: string;
}

const formatDuration = (seconds?: number): string => {
  if (!seconds) return '';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
};

export function TrackCard({ track, isPlaying, onPress, onLongPress, testID }: TrackCardProps) {
  const handleLongPress = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    onLongPress?.();
  };

  return (
    <Pressable
      testID={testID}
      style={[styles.card, isPlaying && styles.cardPlaying]}
      onPress={onPress}
      onLongPress={handleLongPress}
      android_ripple={{ color: '#ffffff10' }}
    >
      {/* Emoji / playing indicator */}
      <View style={styles.leading}>
        <Text style={styles.emoji}>
          {isPlaying ? '▶' : (track.emojis?.[0] ?? '♪')}
        </Text>
      </View>

      {/* Track info */}
      <View style={styles.info}>
        <Text style={[styles.title, isPlaying && styles.titlePlaying]} numberOfLines={1}>
          {track.title}
        </Text>
        <Text style={styles.artist} numberOfLines={1}>
          {track.artist ?? 'Unknown Artist'}
          {track.album ? ` · ${track.album}` : ''}
        </Text>
      </View>

      {/* Metadata */}
      <View style={styles.trailing}>
        {track.elo_rating != null && (
          <Text style={styles.rating}>{Math.round(track.elo_rating)}</Text>
        )}
        <Text style={styles.duration}>{formatDuration(track.duration)}</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#1E1E1E',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#2A2A2A',
  },
  cardPlaying: {
    backgroundColor: '#7C4DFF15',
  },
  leading: {
    width: 36,
    height: 36,
    borderRadius: 8,
    backgroundColor: '#2A2A2A',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  emoji: {
    fontSize: 18,
  },
  info: {
    flex: 1,
    marginRight: 12,
  },
  title: {
    color: '#E0E0E0',
    fontSize: 14,
    fontWeight: '500',
  },
  titlePlaying: {
    color: '#7C4DFF',
  },
  artist: {
    color: '#9E9E9E',
    fontSize: 12,
    marginTop: 2,
  },
  trailing: {
    alignItems: 'flex-end',
    gap: 2,
  },
  rating: {
    color: '#9E9E9E',
    fontSize: 12,
    fontFamily: 'monospace',
  },
  duration: {
    color: '#666',
    fontSize: 11,
    fontFamily: 'monospace',
  },
});
