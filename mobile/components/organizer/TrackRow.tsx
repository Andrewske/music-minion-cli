/**
 * Track row within a bucket — swipe left to unassign.
 * Light haptic on unassign.
 */
import { useCallback } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
  runOnJS,
} from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';

const SWIPE_THRESHOLD = -80;

interface TrackRowProps {
  trackId: number;
  title: string;
  onUnassign: () => void;
}

export function TrackRow({ trackId, title, onUnassign }: TrackRowProps) {
  const translateX = useSharedValue(0);

  const handleUnassign = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    onUnassign();
  }, [onUnassign]);

  const panGesture = Gesture.Pan()
    .activeOffsetX([-10, 10])
    .onUpdate((event) => {
      // Only allow left swipe
      translateX.value = Math.min(0, event.translationX);
    })
    .onEnd((event) => {
      if (event.translationX < SWIPE_THRESHOLD) {
        translateX.value = withTiming(-200, { duration: 150 }, () => {
          runOnJS(handleUnassign)();
          translateX.value = 0;
        });
      } else {
        translateX.value = withSpring(0, { damping: 15 });
      }
    });

  const rowStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: translateX.value }],
  }));

  return (
    <View style={styles.container}>
      {/* Reveal layer behind the row */}
      <View style={styles.revealLayer}>
        <Text style={styles.revealText}>Remove</Text>
      </View>

      <GestureDetector gesture={panGesture}>
        <Animated.View style={[styles.row, rowStyle]}>
          <Text style={styles.title} numberOfLines={1}>
            {title}
          </Text>
          <Text style={styles.trackId}>#{trackId}</Text>
        </Animated.View>
      </GestureDetector>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'relative',
    overflow: 'hidden',
  },
  revealLayer: {
    position: 'absolute',
    right: 0,
    top: 0,
    bottom: 0,
    width: 100,
    backgroundColor: '#CF6679',
    justifyContent: 'center',
    alignItems: 'center',
  },
  revealText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '600',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: '#1E1E1E',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#2A2A2A',
  },
  title: {
    color: '#E0E0E0',
    fontSize: 14,
    flex: 1,
    marginRight: 8,
  },
  trackId: {
    color: '#666',
    fontSize: 11,
    fontFamily: 'monospace',
  },
});
