/**
 * Full player action row: Like · Add · Device · Queue.
 *
 * Like toggles the SoundCloud like (the same durable job a feed Keep queues,
 * without the Keep verdict); local-only tracks can't be liked, so it dims.
 * Add opens the add-to-playlist sheet, Device the device sheet, Queue scrolls
 * to the up-next list.
 */
import { memo } from 'react';
import type { ReactElement } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import * as Haptics from 'expo-haptics';
import Toast from 'react-native-toast-message';
import { Heart, ListMusic, ListPlus, MonitorSpeaker } from 'lucide-react-native';
import type { LucideIcon } from 'lucide-react-native';
import { usePlayerStore } from '../../stores/playerStore';

const LIKED = '#FF5252';
const ACCENT = '#7C4DFF';
const IDLE = '#C8C8C8';

interface PlayerActionRowProps {
  onAdd: () => void;
  onDevices: () => void;
  onQueue: () => void;
}

/** Memoized: callers pass stable (useCallback) handlers. */
export const PlayerActionRow = memo(function PlayerActionRow({ onAdd, onDevices, onQueue }: PlayerActionRowProps): ReactElement {
  const isRemote = usePlayerStore((s) => !s.isThisDeviceActive);
  return (
    <View style={styles.row}>
      <LikeButton />
      <ActionButton icon={ListPlus} label="Add" testID="now-playing-add" onPress={onAdd} />
      <ActionButton icon={MonitorSpeaker} label="Device" testID="now-playing-devices" onPress={onDevices} color={isRemote ? ACCENT : undefined} />
      <ActionButton icon={ListMusic} label="Queue" testID="now-playing-queue" onPress={onQueue} />
    </View>
  );
});

function LikeButton(): ReactElement {
  const canLike = usePlayerStore((s) => Boolean(s.currentTrack?.soundcloud_id));
  const liked = usePlayerStore((s) => Boolean(s.currentTrack?.sc_liked));
  const setLiked = usePlayerStore((s) => s.setLiked);
  const toggle = (): void => {
    setLiked(!liked).catch((err: unknown) => {
      Toast.show({ type: 'error', text1: liked ? "Couldn't unlike" : "Couldn't like", text2: err instanceof Error ? err.message : 'Unknown error' });
    });
  };
  return (
    <ActionButton
      icon={Heart}
      label={liked ? 'Liked' : 'Like'}
      testID="now-playing-like"
      onPress={toggle}
      color={liked ? LIKED : undefined}
      filled={liked}
      selected={liked}
      disabled={!canLike}
    />
  );
}

interface ActionButtonProps {
  icon: LucideIcon;
  label: string;
  testID: string;
  onPress: () => void;
  /** Icon + label color; defaults to the idle grey. */
  color?: string;
  filled?: boolean;
  selected?: boolean;
  disabled?: boolean;
}

function ActionButton({ icon: Icon, label, testID, onPress, color, filled, selected, disabled }: ActionButtonProps): ReactElement {
  const tint = color ?? IDLE;
  const handlePress = (): void => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    onPress();
  };
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected, disabled }}
      onPress={handlePress}
      disabled={disabled}
      android_ripple={{ color: '#FFFFFF1F', borderless: true, radius: 32 }}
      // Static styles: NativeWind's Pressable wrapper drops function styles.
      style={[styles.button, disabled && styles.disabled]}
    >
      <Icon size={24} color={tint} fill={filled ? tint : 'transparent'} strokeWidth={1.75} />
      <Text style={[styles.label, color !== undefined && { color }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    justifyContent: 'space-evenly',
    width: '100%',
    paddingVertical: 4,
    marginBottom: 12,
  },
  button: { minWidth: 64, minHeight: 56, alignItems: 'center', justifyContent: 'center', gap: 4 },
  disabled: { opacity: 0.35 },
  label: { color: '#9E9E9E', fontSize: 11, fontWeight: '500' },
});
