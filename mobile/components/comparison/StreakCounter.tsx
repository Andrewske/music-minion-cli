/**
 * Streak counter — shows consecutive fast votes.
 * Increments when vote happens within 5s of previous.
 * Pure local state, no server tracking.
 */
import { useEffect, useRef } from 'react';
import { Text, StyleSheet } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSequence,
  withSpring,
  withTiming,
} from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';

const STREAK_TIMEOUT_MS = 5000;
const MIN_VISIBLE_STREAK = 3;

interface StreakCounterProps {
  /** Incremented each time a vote fires (comparison count or similar). */
  voteCount: number;
}

export function StreakCounter({ voteCount }: StreakCounterProps) {
  const streakRef = useRef(0);
  const lastVoteTimeRef = useRef(0);
  const scale = useSharedValue(1);
  const displayStreak = useRef(0);

  useEffect(() => {
    if (voteCount === 0) return;

    const now = Date.now();
    const elapsed = now - lastVoteTimeRef.current;

    if (elapsed < STREAK_TIMEOUT_MS && lastVoteTimeRef.current > 0) {
      streakRef.current += 1;
    } else {
      streakRef.current = 1;
    }

    lastVoteTimeRef.current = now;
    displayStreak.current = streakRef.current;

    if (streakRef.current >= MIN_VISIBLE_STREAK) {
      // Pop animation
      scale.value = withSequence(
        withSpring(1.3, { damping: 5, stiffness: 300 }),
        withTiming(1, { duration: 200 })
      );

      // Heavier haptic on milestone streaks
      if (streakRef.current % 5 === 0) {
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
      }
    }
  }, [voteCount, scale]);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
  }));

  if (displayStreak.current < MIN_VISIBLE_STREAK) {
    return null;
  }

  return (
    <Animated.View style={[styles.container, animatedStyle]}>
      <Text style={styles.fire}>🔥</Text>
      <Text style={styles.count}>{displayStreak.current}</Text>
      <Text style={styles.label}>in a row!</Text>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 8,
  },
  fire: {
    fontSize: 20,
  },
  count: {
    color: '#FF9800',
    fontSize: 18,
    fontWeight: 'bold',
    fontFamily: 'monospace',
  },
  label: {
    color: '#9E9E9E',
    fontSize: 14,
  },
});
