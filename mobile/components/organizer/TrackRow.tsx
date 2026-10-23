/**
 * Track row within an expanded bucket — title on the left, remove icon on the right.
 */
import { useCallback } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import * as Haptics from 'expo-haptics';

interface TrackRowProps {
  title: string;
  onUnassign: () => void;
  testID?: string;
}

export function TrackRow({ title, onUnassign, testID }: TrackRowProps): React.JSX.Element {
  const handleUnassign = useCallback((): void => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    onUnassign();
  }, [onUnassign]);

  return (
    <View style={styles.row}>
      <Text style={styles.title} numberOfLines={1}>
        {title}
      </Text>
      <Pressable
        testID={testID}
        accessibilityRole="button"
        accessibilityLabel={`Remove ${title} from bucket`}
        hitSlop={8}
        style={({ pressed }) => [styles.removeBtn, pressed && styles.removeBtnPressed]}
        onPress={handleUnassign}
      >
        <Text style={styles.removeIcon}>✕</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingLeft: 16,
    paddingRight: 8,
    paddingVertical: 6,
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
  removeBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  removeBtnPressed: {
    backgroundColor: '#3E1E1E',
  },
  removeIcon: {
    color: '#CF6679',
    fontSize: 16,
    fontWeight: '600',
  },
});
