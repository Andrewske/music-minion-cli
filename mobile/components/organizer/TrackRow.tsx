/**
 * Track row within an expanded bucket. Swipe left to remove it from the
 * bucket: the row slides over a red "Remove" panel, and releasing past the
 * panel's width commits. The screen then offers Undo (see UndoSnackbar).
 * TalkBack users get the same thing as a "Remove from bucket" action.
 */
import { useCallback } from 'react';
import type { ReactElement } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import type { AccessibilityActionEvent } from 'react-native';
import ReanimatedSwipeable from 'react-native-gesture-handler/ReanimatedSwipeable';
import Animated, { interpolate, Extrapolation, useAnimatedStyle } from 'react-native-reanimated';
import type { SharedValue } from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';
import { Trash2 } from 'lucide-react-native';

/** Width of the revealed panel; dragging this far and releasing removes. */
const ACTION_WIDTH = 112;
const ACCESSIBILITY_ACTIONS = [{ name: 'remove', label: 'Remove from bucket' }];

interface TrackRowProps {
  title: string;
  onRemove: () => void;
  testID?: string;
}

export function TrackRow({ title, onRemove, testID }: TrackRowProps): ReactElement {
  const handleRemove = useCallback((): void => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    onRemove();
  }, [onRemove]);

  const handleAction = useCallback(
    (e: AccessibilityActionEvent): void => {
      if (e.nativeEvent.actionName === 'remove') handleRemove();
    },
    [handleRemove],
  );

  return (
    <ReanimatedSwipeable
      testID={testID}
      rightThreshold={ACTION_WIDTH * 0.9}
      overshootRight={false}
      dragOffsetFromRightEdge={16}
      renderRightActions={(progress) => <RemoveAction progress={progress} />}
      onSwipeableOpen={handleRemove}
      containerStyle={styles.container}
    >
      <View
        style={styles.row}
        accessible
        accessibilityLabel={title}
        accessibilityHint="Swipe left to remove from bucket"
        accessibilityActions={ACCESSIBILITY_ACTIONS}
        onAccessibilityAction={handleAction}
      >
        <Text style={styles.title} numberOfLines={1}>
          {title}
        </Text>
      </View>
    </ReanimatedSwipeable>
  );
}

/** The red panel under the row; the icon grows in as the row slides away. */
function RemoveAction({ progress }: { progress: SharedValue<number> }): ReactElement {
  const iconStyle = useAnimatedStyle(() => ({
    opacity: interpolate(progress.value, [0, 0.4, 1], [0, 0.6, 1], Extrapolation.CLAMP),
    transform: [{ scale: interpolate(progress.value, [0, 1], [0.7, 1], Extrapolation.CLAMP) }],
  }));

  return (
    <View style={styles.action}>
      <Animated.View style={[styles.actionContent, iconStyle]}>
        <Trash2 size={20} color="#FFFFFF" />
        <Text style={styles.actionText}>Remove</Text>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#8E2F3F',
  },
  row: {
    minHeight: 48,
    justifyContent: 'center',
    paddingHorizontal: 16,
    backgroundColor: '#1E1E1E',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#2A2A2A',
  },
  title: {
    color: '#E0E0E0',
    fontSize: 14,
  },
  action: {
    width: ACTION_WIDTH,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#8E2F3F',
  },
  actionContent: {
    alignItems: 'center',
    gap: 2,
  },
  actionText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '600',
  },
});
