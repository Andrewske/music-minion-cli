/**
 * Full player action row: Device · Queue.
 *
 * Device opens the device sheet; Queue scrolls to the up-next list.
 * # TODO: add Like and Add to playlist once the backend has endpoints for them.
 */
import { memo } from 'react';
import type { ReactElement } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import * as Haptics from 'expo-haptics';
import { ListMusic, MonitorSpeaker } from 'lucide-react-native';
import type { LucideIcon } from 'lucide-react-native';
import { usePlayerStore } from '../../stores/playerStore';

interface PlayerActionRowProps {
  onDevices: () => void;
  onQueue: () => void;
}

/** Memoized: callers pass stable (useCallback) handlers. */
export const PlayerActionRow = memo(function PlayerActionRow({ onDevices, onQueue }: PlayerActionRowProps): ReactElement {
  const isRemote = usePlayerStore((s) => !s.isThisDeviceActive);
  return (
    <View style={styles.row}>
      <ActionButton icon={MonitorSpeaker} label="Device" testID="now-playing-devices" onPress={onDevices} highlighted={isRemote} />
      <ActionButton icon={ListMusic} label="Queue" testID="now-playing-queue" onPress={onQueue} />
    </View>
  );
});

interface ActionButtonProps {
  icon: LucideIcon;
  label: string;
  testID: string;
  onPress: () => void;
  highlighted?: boolean;
}

function ActionButton({ icon: Icon, label, testID, onPress, highlighted }: ActionButtonProps): ReactElement {
  const color = highlighted ? '#7C4DFF' : '#C8C8C8';
  const handlePress = (): void => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    onPress();
  };
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={label}
      onPress={handlePress}
      android_ripple={{ color: '#FFFFFF1F', borderless: true, radius: 32 }}
      style={styles.button}
    >
      <Icon size={24} color={color} strokeWidth={1.75} />
      <Text style={[styles.label, highlighted && styles.labelHighlighted]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 48,
    width: '100%',
    paddingVertical: 4,
    marginBottom: 12,
  },
  button: { minWidth: 64, minHeight: 56, alignItems: 'center', justifyContent: 'center', gap: 4 },
  label: { color: '#9E9E9E', fontSize: 11, fontWeight: '500' },
  labelHighlighted: { color: '#7C4DFF' },
});
