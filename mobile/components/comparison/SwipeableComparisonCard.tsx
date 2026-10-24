/**
 * Swipeable track card for comparison voting.
 *
 * Tap = play / pause this track through the global player.
 * Swipe right = this track wins.
 * Card fills the height its parent gives it (flex: 1); when that height is
 * small, art and genres are dropped so the session fits one screen.
 */
import { useCallback, useEffect, useState } from 'react';
import { View, Text, StyleSheet, Dimensions } from 'react-native';
import type { LayoutChangeEvent } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
  runOnJS,
  interpolate,
  Extrapolation,
  type SharedValue,
} from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';
import { Music, Pause, Play } from 'lucide-react-native';
import type { TrackInfo } from '@music-minion/shared';
import { usePlayerStore, getCurrentPosition } from '../../stores/playerStore';
import {
  formatDuration,
  playbackFraction,
  type CardPlayState,
} from '../../features/comparison/comparisonState';

const SCREEN_WIDTH = Dimensions.get('window').width;
const SWIPE_THRESHOLD = SCREEN_WIDTH * 0.3;
const MAX_ROTATION = 15; // degrees
/** Below this card height, hide art + genres. */
const COMPACT_HEIGHT = 240;
const PROGRESS_TICK_MS = 500;

interface SwipeableComparisonCardProps {
  track: TrackInfo;
  label: 'A' | 'B';
  onVote: () => void;
  onPress: () => void;
  playState: CardPlayState;
  /** Another device holds playback (audio is not on this phone). */
  playingElsewhere?: boolean;
  disabled?: boolean;
}

/** Live playback fraction for the active card; ticks only while playing. */
function useCardProgress(active: boolean, durationSec: number | undefined): number {
  const read = useCallback(
    (): number => playbackFraction(getCurrentPosition(usePlayerStore.getState()), durationSec),
    [durationSec],
  );
  const [fraction, setFraction] = useState<number>(0);
  const isPlaying = usePlayerStore((s) => s.isPlaying);
  const positionMs = usePlayerStore((s) => s.positionMs);

  useEffect(() => {
    if (!active) return;
    setFraction(read());
    if (!isPlaying) return;
    const id = setInterval(() => setFraction(read()), PROGRESS_TICK_MS);
    return () => clearInterval(id);
  }, [active, isPlaying, positionMs, read]);

  return active ? fraction : 0;
}

interface SwipeCard {
  gesture: ReturnType<typeof Gesture.Race>;
  translateX: SharedValue<number>;
}

function useSwipeCard(onVote: () => void, onPress: () => void, disabled: boolean): SwipeCard {
  const translateX = useSharedValue(0);

  const triggerVote = useCallback((): void => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    onVote();
  }, [onVote]);

  const triggerPress = useCallback((): void => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    onPress();
  }, [onPress]);

  const pan = Gesture.Pan()
    .enabled(!disabled)
    .activeOffsetX([-12, 12])
    .onUpdate((event) => {
      translateX.value = event.translationX;
    })
    .onEnd((event) => {
      if (event.translationX > SWIPE_THRESHOLD) {
        translateX.value = withTiming(SCREEN_WIDTH, { duration: 200 }, () => {
          runOnJS(triggerVote)();
          translateX.value = 0;
        });
      } else {
        translateX.value = withSpring(0, { damping: 15, stiffness: 150 });
      }
    });

  const tap = Gesture.Tap().onEnd((_event, success) => {
    if (success) runOnJS(triggerPress)();
  });

  return { gesture: Gesture.Race(pan, tap), translateX };
}

export function SwipeableComparisonCard({
  track,
  label,
  onVote,
  onPress,
  playState,
  playingElsewhere = false,
  disabled = false,
}: SwipeableComparisonCardProps): React.JSX.Element {
  const { gesture, translateX } = useSwipeCard(onVote, onPress, disabled);
  const [compact, setCompact] = useState<boolean>(false);
  const fraction = useCardProgress(playState !== 'idle', track.duration);

  const handleLayout = useCallback((e: LayoutChangeEvent): void => {
    setCompact(e.nativeEvent.layout.height < COMPACT_HEIGHT);
  }, []);

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
      transform: [{ translateX: translateX.value }, { rotate: `${rotation}deg` }],
      opacity,
    };
  });

  const winIndicatorStyle = useAnimatedStyle(() => ({
    opacity: interpolate(translateX.value, [0, SWIPE_THRESHOLD], [0, 1], Extrapolation.CLAMP),
  }));

  const isActive = playState !== 'idle';

  return (
    <GestureDetector gesture={gesture}>
      <Animated.View
        testID={`comparison-card-${label.toLowerCase()}`}
        accessibilityRole="button"
        accessibilityLabel={`${playState === 'playing' ? 'Pause' : 'Play'} ${track.title}`}
        accessibilityState={{ selected: isActive }}
        onLayout={handleLayout}
        style={[styles.card, isActive && styles.cardActive, cardStyle]}
      >
        <Animated.View style={[styles.winIndicator, winIndicatorStyle]}>
          <Text style={styles.winText}>WINNER</Text>
        </Animated.View>

        <View style={styles.labelBadge}>
          <Text style={styles.labelText}>{label}</Text>
        </View>

        <View style={styles.content}>
          {!compact && (
            <View style={styles.artPlaceholder}>
              {track.emojis?.[0] ? (
                <Text style={styles.artEmoji}>{track.emojis[0]}</Text>
              ) : (
                <Music size={28} color="#666" />
              )}
            </View>
          )}
          <Text style={styles.title} numberOfLines={2}>{track.title}</Text>
          <Text style={styles.artist} numberOfLines={1}>{track.artist ?? 'Unknown Artist'}</Text>
          <CardStats track={track} />
          {!compact && <CardGenres track={track} />}
        </View>

        <PlayStatus
          label={label}
          playState={playState}
          playingElsewhere={playingElsewhere}
          fraction={fraction}
        />
      </Animated.View>
    </GestureDetector>
  );
}

function CardStats({ track }: { track: TrackInfo }): React.JSX.Element {
  return (
    <View style={styles.statsRow}>
      <Stat value={track.rating?.toFixed(0) ?? '--'} label="Rating" />
      <Stat value={`${track.wins ?? 0}W / ${track.losses ?? 0}L`} label="Record" />
      <Stat value={formatDuration(track.duration)} label="Duration" />
    </View>
  );
}

function Stat({ value, label }: { value: string; label: string }): React.JSX.Element {
  return (
    <View style={styles.stat}>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function CardGenres({ track }: { track: TrackInfo }): React.JSX.Element | null {
  if (!track.genres || track.genres.length === 0) return null;
  return (
    <View style={styles.genres}>
      {track.genres.slice(0, 3).map((g) => (
        <View key={g.id} style={styles.genreTag}>
          <Text style={styles.genreText}>
            {g.emoji_id ? `${g.emoji_id} ` : ''}{g.name}
          </Text>
        </View>
      ))}
    </View>
  );
}

interface PlayStatusProps {
  label: 'A' | 'B';
  playState: CardPlayState;
  playingElsewhere: boolean;
  fraction: number;
}

function PlayStatus({ label, playState, playingElsewhere, fraction }: PlayStatusProps): React.JSX.Element {
  const Icon = playState === 'playing' ? Pause : Play;
  const hint =
    playState === 'idle'
      ? 'Tap to play · swipe right = winner'
      : playingElsewhere
        ? 'Playing on another device'
        : playState === 'playing'
          ? 'Playing · tap to pause'
          : 'Paused · tap to resume';

  return (
    <View style={styles.playStatus}>
      <View style={styles.playRow}>
        <View testID={`comparison-card-${label.toLowerCase()}-${playState}`} style={styles.playIcon}>
          <Icon size={16} color={playState === 'idle' ? '#9E9E9E' : '#7C4DFF'} />
        </View>
        <Text style={styles.hint} numberOfLines={1}>{hint}</Text>
      </View>
      <View style={styles.progressTrack}>
        <View style={[styles.progressFill, { width: `${fraction * 100}%` }]} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    flex: 1,
    backgroundColor: '#1E1E1E',
    borderRadius: 16,
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 10,
    marginHorizontal: 8,
    borderWidth: 1,
    borderColor: '#333',
    overflow: 'hidden',
    justifyContent: 'space-between',
  },
  cardActive: {
    borderColor: '#7C4DFF',
  },
  winIndicator: {
    position: 'absolute',
    top: 12,
    right: 12,
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
    top: 12,
    left: 12,
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#7C4DFF',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10,
  },
  labelText: {
    color: '#fff',
    fontWeight: 'bold',
    fontSize: 14,
  },
  content: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 24,
  },
  artPlaceholder: {
    width: 64,
    height: 64,
    borderRadius: 12,
    backgroundColor: '#2A2A2A',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 10,
  },
  artEmoji: {
    fontSize: 30,
  },
  title: {
    color: '#E0E0E0',
    fontSize: 17,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 2,
  },
  artist: {
    color: '#9E9E9E',
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 10,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    width: '100%',
  },
  stat: {
    alignItems: 'center',
  },
  statValue: {
    color: '#E0E0E0',
    fontSize: 13,
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
    marginTop: 10,
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
  playStatus: {
    gap: 6,
    marginTop: 8,
  },
  playRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  playIcon: {
    width: 20,
    alignItems: 'center',
  },
  hint: {
    color: '#777',
    fontSize: 12,
    flex: 1,
  },
  progressTrack: {
    height: 3,
    backgroundColor: '#333',
    borderRadius: 2,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#7C4DFF',
  },
});
