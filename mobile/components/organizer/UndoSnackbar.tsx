/**
 * Snackbar pinned to the bottom of the organizer session list after a track
 * is added to or removed from a bucket. One explicit Undo button (48dp),
 * instead of a toast you have to know to tap.
 */
import type { ReactElement } from 'react';
import { Text, Pressable, StyleSheet } from 'react-native';
import Animated, { FadeInDown, FadeOutDown } from 'react-native-reanimated';
import { Undo2 } from 'lucide-react-native';
import { undoMessage } from '../../features/organizer/undoState';
import type { UndoAction } from '../../features/organizer/undoState';

interface UndoSnackbarProps {
  action: UndoAction | null;
  onUndo: () => void;
}

export function UndoSnackbar({ action, onUndo }: UndoSnackbarProps): ReactElement | null {
  if (!action) return null;
  return (
    <Animated.View
      key={action.id}
      testID="undo-snackbar"
      entering={FadeInDown.duration(180)}
      exiting={FadeOutDown.duration(140)}
      style={styles.bar}
      accessibilityLiveRegion="polite"
    >
      <Text style={styles.message} numberOfLines={1}>
        {undoMessage(action)}
      </Text>
      <Pressable
        testID="undo-btn"
        accessibilityRole="button"
        accessibilityLabel="Undo"
        android_ripple={{ color: '#7C4DFF40' }}
        style={styles.undo}
        onPress={onUndo}
      >
        <Undo2 size={18} color="#C9B8FF" />
        <Text style={styles.undoText}>Undo</Text>
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  bar: {
    position: 'absolute',
    left: 12,
    right: 12,
    bottom: 10,
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 52,
    paddingLeft: 16,
    paddingRight: 4,
    borderRadius: 12,
    backgroundColor: '#2A2A2A',
    borderWidth: 1,
    borderColor: '#3A3A3A',
    elevation: 6,
  },
  message: {
    flex: 1,
    color: '#E0E0E0',
    fontSize: 14,
    marginRight: 8,
  },
  undo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    minHeight: 44,
    paddingHorizontal: 14,
    borderRadius: 10,
    overflow: 'hidden',
  },
  undoText: {
    color: '#C9B8FF',
    fontSize: 15,
    fontWeight: '700',
  },
});
