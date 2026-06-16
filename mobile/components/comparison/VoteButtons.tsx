/**
 * Fallback tap-to-vote buttons below the swipe cards.
 * Large touch targets (56dp) per Material Design.
 */
import { View, Text, Pressable, StyleSheet } from 'react-native';
import * as Haptics from 'expo-haptics';

interface VoteButtonsProps {
  trackATitle: string;
  trackBTitle: string;
  onVoteA: () => void;
  onVoteB: () => void;
  disabled?: boolean;
}

export function VoteButtons({
  trackATitle,
  trackBTitle,
  onVoteA,
  onVoteB,
  disabled = false,
}: VoteButtonsProps) {
  const handleVoteA = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    onVoteA();
  };

  const handleVoteB = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    onVoteB();
  };

  return (
    <View style={styles.container}>
      <Pressable
        testID="vote-a"
        style={[styles.button, styles.buttonA, disabled && styles.disabled]}
        onPress={handleVoteA}
        disabled={disabled}
      >
        <Text style={styles.buttonLabel}>A</Text>
        <Text style={styles.buttonTitle} numberOfLines={1}>
          {trackATitle}
        </Text>
        <Text style={styles.buttonAction}>wins</Text>
      </Pressable>

      <Pressable
        testID="vote-b"
        style={[styles.button, styles.buttonB, disabled && styles.disabled]}
        onPress={handleVoteB}
        disabled={disabled}
      >
        <Text style={styles.buttonLabel}>B</Text>
        <Text style={styles.buttonTitle} numberOfLines={1}>
          {trackBTitle}
        </Text>
        <Text style={styles.buttonAction}>wins</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    gap: 12,
    paddingHorizontal: 16,
  },
  button: {
    flex: 1,
    height: 56,
    borderRadius: 12,
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    gap: 8,
  },
  buttonA: {
    backgroundColor: '#1B5E20',
  },
  buttonB: {
    backgroundColor: '#1A237E',
  },
  disabled: {
    opacity: 0.5,
  },
  buttonLabel: {
    color: '#fff',
    fontWeight: 'bold',
    fontSize: 18,
    width: 24,
  },
  buttonTitle: {
    color: '#E0E0E0',
    fontSize: 14,
    flex: 1,
  },
  buttonAction: {
    color: '#9E9E9E',
    fontSize: 12,
    fontStyle: 'italic',
  },
});
