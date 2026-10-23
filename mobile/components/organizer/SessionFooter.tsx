/**
 * Sticky session actions — always visible below the track list.
 * Sits above the global PlayerBar, which already pads for the bottom inset.
 */
import { View, Text, Pressable, ActivityIndicator } from 'react-native';

interface SessionFooterProps {
  onApply: () => void;
  onFinalize: () => void;
  onDiscard: () => void;
  isApplying: boolean;
  isFinalizing: boolean;
}

export function SessionFooter({
  onApply,
  onFinalize,
  onDiscard,
  isApplying,
  isFinalizing,
}: SessionFooterProps): React.JSX.Element {
  return (
    <View className="flex-row gap-2 px-4 py-2 border-t border-neutral-800 bg-background">
      <Pressable
        testID="organizer-discard-btn"
        className="bg-surface rounded-lg px-4 py-3 items-center justify-center border border-red-900 active:opacity-70"
        onPress={onDiscard}
      >
        <Text className="text-error text-sm font-medium">Discard</Text>
      </Pressable>
      <Pressable
        testID="organizer-finalize-btn"
        className="bg-surface rounded-lg px-4 py-3 items-center justify-center border border-neutral-700 active:opacity-70"
        onPress={onFinalize}
        disabled={isFinalizing}
      >
        {isFinalizing ? (
          <ActivityIndicator color="#E0E0E0" size="small" />
        ) : (
          <Text className="text-text-primary text-sm font-medium">Finalize</Text>
        )}
      </Pressable>
      <Pressable
        testID="organizer-apply-btn"
        className="flex-1 bg-primary rounded-lg py-3 items-center justify-center active:opacity-80"
        onPress={onApply}
        disabled={isApplying}
      >
        {isApplying ? (
          <ActivityIndicator color="#fff" size="small" />
        ) : (
          <Text className="text-white text-sm font-bold">Apply Order</Text>
        )}
      </Pressable>
    </View>
  );
}
