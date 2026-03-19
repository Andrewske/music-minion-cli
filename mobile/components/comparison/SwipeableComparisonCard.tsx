/**
 * Swipeable track card for comparison voting.
 *
 * Swipe right = this track wins
 * Swipe left = other track wins (vote for opponent)
 * Card rotates with swipe velocity for tactile feedback.
 * Haptic: medium on vote confirm.
 */
import { useCallback } from 'react';
import { View, Text, StyleSheet, Dimensions } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
  runOnJS,
  interpolate,
  Extrapolation,
} from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';
import type { TrackInfo } from '@music-minion/shared';

const SCREEN_WIDTH = Dimensions.get('window').width;
const SWIPE_THRESHOLD = SCREEN_WIDTH * 0.3;
const MAX_ROTATION = 15; // degrees

interface SwipeableComparisonCardProps {
  track: TrackInfo;
  label: 'A' | 'B';
  onVote: () => void;
  disabled?: boolean;
}

export function SwipeableComparisonCard({
  track,
  label,
  onVote,
  disabled = false,
}: SwipeableComparisonCardProps) {
  const translateX = useSharedValue(0);
  const isActive = useSharedValue(false);

  const triggerVote = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    onVote();
  }, [onVote]);

  const resetPosition = useCallback(() => {
    translateX.value = withSpring(0, { damping: 15, stiffness: 150 });
  }, [translateX]);

  const panGesture = Gesture.Pan()
    .enabled(!disabled)
    .onStart(() => {
      isActive.value = true;
    })
    .onUpdate((event) => {
      translateX.value = event.translationX;
    })
    .onEnd((event) => {
      isActive.value = false;

      if (event.translationX > SWIPE_THRESHOLD) {
        // Swipe right — this track wins
        translateX.value = withTiming(SCREEN_WIDTH, { duration: 200 }, () => {
          runOnJS(triggerVote)();
          translateX.value = 0;
        });
      } else if (event.translationX < -SWIPE_THRESHOLD) {
        // Swipe left — opponent wins (same effect: vote for this card's opponent)
        translateX.value = withTiming(-SCREEN_WIDTH, { duration: 200 }, () => {
          translateX.value = 0;
        });
      } else {
        runOnJS(resetPosition)();
      }
    });

  const cardStyle = useAnimatedStyle(() => {
    const rotation = interpolate(
      translateX.value,
      [-SCREEN_WIDTH, 0, SCREEN_WIDTH],
      [-MAX_ROTATION, 0, MAX_ROTATION],
      Extrapolation.CLAMP
    );

    const opacity = interpolate(
      Math.abs(translateX.value),
      [0, SWIPE_THRESHOLD, SCREEN_WIDTH],
      [1, 0.8, 0.3],
      Extrapolation.CLAMP
    );

    return {
      transform: [
        { translateX: translateX.value },
        { rotate: `${rotation}deg` },
      ],
      opacity,
    };
  });

  // Vote indicator overlay
  const winIndicatorStyle = useAnimatedStyle(() => ({
    opacity: interpolate(
      translateX.value,
      [0, SWIPE_THRESHOLD],
      [0, 1],
      Extrapolation.CLAMP
    ),
  }));

  const formatDuration = (seconds?: number): string => {
    if (!seconds) return '--:--';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <GestureDetector gesture={panGesture}>
      <Animated.View style={[styles.card, cardStyle]}>
        {/* Win indicator */}
        <Animated.View style={[styles.winIndicator, winIndicatorStyle]}>
          <Text style={styles.winText}>WINNER</Text>
        </Animated.View>

        {/* Label badge */}
        <View style={styles.labelBadge}>
          <Text style={styles.labelText}>{label}</Text>
        </View>

        {/* Track info */}
        <View style={styles.content}>
          {/* Album art placeholder */}
          <View style={styles.artPlaceholder}>
            <Text style={styles.artEmoji}>
              {track.emojis?.[0] ?? '♪'}
            </Text>
          </View>

          <Text style={styles.title} numberOfLines={2}>
            {track.title}
          </Text>
          <Text style={styles.artist} numberOfLines={1}>
            {track.artist ?? 'Unknown Artist'}
          </Text>

          {/* Stats row */}
          <View style={styles.statsRow}>
            <View style={styles.stat}>
              <Text style={styles.statValue}>
                {track.rating?.toFixed(0) ?? '--'}
              </Text>
              <Text style={styles.statLabel}>Rating</Text>
            </View>
            <View style={styles.stat}>
              <Text style={styles.statValue}>
                {track.wins ?? 0}W / {track.losses ?? 0}L
              </Text>
              <Text style={styles.statLabel}>Record</Text>
            </View>
            <View style={styles.stat}>
              <Text style={styles.statValue}>
                {formatDuration(track.duration)}
              </Text>
              <Text style={styles.statLabel}>Duration</Text>
            </View>
          </View>

          {/* Genre tags */}
          {track.genres && track.genres.length > 0 && (
            <View style={styles.genres}>
              {track.genres.slice(0, 3).map((g) => (
                <View key={g.id} style={styles.genreTag}>
                  <Text style={styles.genreText}>
                    {g.emoji_id ? `${g.emoji_id} ` : ''}{g.name}
                  </Text>
                </View>
              ))}
            </View>
          )}
        </View>

        {/* Swipe hint */}
        <Text style={styles.hint}>
          Swipe right = winner
        </Text>
      </Animated.View>
    </GestureDetector>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#1E1E1E',
    borderRadius: 16,
    padding: 20,
    marginHorizontal: 8,
    borderWidth: 1,
    borderColor: '#333',
    position: 'relative',
    overflow: 'hidden',
  },
  winIndicator: {
    position: 'absolute',
    top: 16,
    right: 16,
    backgroundColor: '#4CAF50',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 8,
    zIndex: 10,
  },
  winText: {
    color: '#fff',
    fontWeight: 'bold',
    fontSize: 12,
    letterSpacing: 1,
  },
  labelBadge: {
    position: 'absolute',
    top: 16,
    left: 16,
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#7C4DFF',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10,
  },
  labelText: {
    color: '#fff',
    fontWeight: 'bold',
    fontSize: 16,
  },
  content: {
    alignItems: 'center',
    paddingTop: 24,
  },
  artPlaceholder: {
    width: 80,
    height: 80,
    borderRadius: 12,
    backgroundColor: '#2A2A2A',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  artEmoji: {
    fontSize: 36,
  },
  title: {
    color: '#E0E0E0',
    fontSize: 18,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 4,
  },
  artist: {
    color: '#9E9E9E',
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 16,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    width: '100%',
    marginBottom: 12,
  },
  stat: {
    alignItems: 'center',
  },
  statValue: {
    color: '#E0E0E0',
    fontSize: 14,
    fontFamily: 'monospace',
    fontWeight: '600',
  },
  statLabel: {
    color: '#666',
    fontSize: 11,
    marginTop: 2,
  },
  genres: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 6,
  },
  genreTag: {
    backgroundColor: '#2A2A2A',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  genreText: {
    color: '#9E9E9E',
    fontSize: 12,
  },
  hint: {
    color: '#555',
    fontSize: 11,
    textAlign: 'center',
    marginTop: 12,
  },
});
