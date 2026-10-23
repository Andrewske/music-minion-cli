/**
 * Comparison session header: exit (✕), playlist name, session progress, streak.
 */
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { StreakCounter } from './StreakCounter';
import { formatSessionProgress } from '../../features/comparison/comparisonState';

interface SessionHeaderProps {
  playlistName: string;
  voteCount: number;
  onExit: () => void;
}

export function SessionHeader({ playlistName, voteCount, onExit }: SessionHeaderProps): React.JSX.Element {
  return (
    <View style={styles.container}>
      <Pressable
        testID="comparison-exit"
        accessibilityRole="button"
        accessibilityLabel="Exit comparison session"
        onPress={onExit}
        hitSlop={8}
        style={styles.exit}
      >
        <Text style={styles.exitIcon}>✕</Text>
      </Pressable>
      <View style={styles.titleBlock}>
        <Text testID="comparison-playlist-name" style={styles.title} numberOfLines={1}>
          {playlistName}
        </Text>
        <Text testID="comparison-session-progress" style={styles.progress}>
          {formatSessionProgress(voteCount)}
        </Text>
      </View>
      <StreakCounter voteCount={voteCount} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 6,
    gap: 8,
    minHeight: 52,
  },
  exit: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  exitIcon: {
    color: '#E0E0E0',
    fontSize: 20,
  },
  titleBlock: {
    flex: 1,
  },
  title: {
    color: '#E0E0E0',
    fontSize: 17,
    fontWeight: 'bold',
  },
  progress: {
    color: '#9E9E9E',
    fontSize: 12,
    marginTop: 2,
  },
});
