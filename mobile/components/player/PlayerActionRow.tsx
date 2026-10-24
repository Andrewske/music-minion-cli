/**
 * Full player action row: Like · Add to playlist · Device · Queue.
 *
 * Like and Add are rendered disabled: @music-minion/shared has no like or
 * add-track-to-playlist API to call. Device opens the device sheet; Queue
 * scrolls to the up-next list.
 */
import type { ReactElement } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import * as Haptics from 'expo-haptics';
import { Heart, ListMusic, ListPlus, MonitorSpeaker } from 'lucide-react-native';
import type { LucideIcon } from 'lucide-react-native';
import { usePlayerStore } from '../../stores/playerStore';

interface PlayerActionRowProps {
  onDevices: () => void;
  onQueue: () => void;
}

export function PlayerActionRow({ onDevices, onQueue }: PlayerActionRowProps): ReactElement {
  const isRemote = usePlayerStore((s) => !s.isThisDeviceActive);
  return (
    <View style={styles.row}>
      <ActionButton icon={Heart} label="Like" testID="now-playing-like" disabledReason="Liking isn't available yet" />
      <ActionButton icon={ListPlus} label="Add" testID="now-playing-add" disabledReason="Adding to a playlist isn't available yet" />
      <ActionButton icon={MonitorSpeaker} label="Device" testID="now-playing-devices" onPress={onDevices} highlighted={isRemote} />
      <ActionButton icon={ListMusic} label="Queue" testID="now-playing-queue" onPress={onQueue} />
    </View>
  );
}

interface ActionButtonProps {
  icon: LucideIcon;
  label: string;
  testID: string;
  onPress?: () => void;
  /** No handler: render disabled and announce why. */
  disabledReason?: string;
  highlighted?: boolean;
}

function ActionButton({ icon: Icon, label, testID, onPress, disabledReason, highlighted }: ActionButtonProps): ReactElement {
  const disabled = !onPress;
  const color = highlighted ? '#7C4DFF' : '#C8C8C8';
  const handlePress = (): void => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    onPress?.();
  };
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={disabled ? `${label}. ${disabledReason ?? 'Not available'}` : label}
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={handlePress}
      android_ripple={{ color: '#FFFFFF1F', borderless: true, radius: 32 }}
      style={[styles.button, disabled && styles.disabled]}
    >
      <Icon size={24} color={color} strokeWidth={1.75} />
      <Text style={[styles.label, highlighted && styles.labelHighlighted]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    width: '100%',
    paddingVertical: 4,
    marginBottom: 12,
  },
  button: { minWidth: 64, minHeight: 56, alignItems: 'center', justifyContent: 'center', gap: 4 },
  disabled: { opacity: 0.35 },
  label: { color: '#9E9E9E', fontSize: 11, fontWeight: '500' },
  labelHighlighted: { color: '#7C4DFF' },
});
