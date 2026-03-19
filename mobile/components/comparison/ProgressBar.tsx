/**
 * Animated progress bar for comparison completion.
 */
import { View, Text, StyleSheet } from 'react-native';
import Animated, {
  useAnimatedStyle,
  withTiming,
} from 'react-native-reanimated';
import type { ComparisonProgress } from '@music-minion/shared';

interface ProgressBarProps {
  progress: ComparisonProgress | null;
}

export function ProgressBar({ progress }: ProgressBarProps) {
  if (!progress) return null;

  const widthStyle = useAnimatedStyle(() => ({
    width: withTiming(`${Math.min(progress.percentage, 100)}%`, { duration: 300 }),
  }));

  return (
    <View style={styles.container}>
      <View style={styles.barBackground}>
        <Animated.View style={[styles.barFill, widthStyle]} />
      </View>
      <Text style={styles.text}>
        {progress.compared} / {progress.total} ({progress.percentage.toFixed(1)}%)
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 16,
    gap: 4,
  },
  barBackground: {
    height: 4,
    backgroundColor: '#333',
    borderRadius: 2,
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    backgroundColor: '#7C4DFF',
    borderRadius: 2,
  },
  text: {
    color: '#9E9E9E',
    fontSize: 12,
    fontFamily: 'monospace',
    textAlign: 'center',
  },
});
