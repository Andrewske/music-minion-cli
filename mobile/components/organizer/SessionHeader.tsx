/**
 * Organizer session header — back to picker, playlist name, progress counts.
 */
import { View, Text, Pressable } from 'react-native';
import type { SessionCounts } from '../../features/organizer/organizerState';

interface SessionHeaderProps {
  playlistName: string;
  counts: SessionCounts;
  onBack: () => void;
}

export function SessionHeader({ playlistName, counts, onBack }: SessionHeaderProps): React.JSX.Element {
  return (
    <View className="px-4 pt-4 pb-3 border-b border-neutral-800">
      <Pressable
        testID="organizer-back-btn"
        accessibilityRole="button"
        accessibilityLabel="Back to playlists"
        hitSlop={12}
        className="self-start py-1 active:opacity-70"
        onPress={onBack}
      >
        <Text className="text-primary text-base">← Playlists</Text>
      </Pressable>
      <Text testID="organizer-session-title" className="text-text-primary text-xl font-bold mt-1" numberOfLines={1}>
        {playlistName}
      </Text>
      <Text testID="organizer-session-counts" className="text-text-secondary text-sm mt-0.5">
        {counts.assigned}/{counts.total} sorted · {counts.unassigned} left · {counts.buckets} buckets
      </Text>
    </View>
  );
}
