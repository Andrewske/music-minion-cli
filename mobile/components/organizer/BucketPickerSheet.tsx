/**
 * Bottom sheet for choosing which bucket a track goes into.
 * Nothing is assigned until the user taps a bucket; tapping the backdrop cancels.
 */
import { Modal, View, Text, Pressable, ScrollView, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { Bucket } from '@music-minion/shared';

interface BucketPickerSheetProps {
  visible: boolean;
  trackLabel: string;
  buckets: readonly Bucket[];
  onPick: (bucket: Bucket) => void;
  onClose: () => void;
}

export function BucketPickerSheet({
  visible,
  trackLabel,
  buckets,
  onPick,
  onClose,
}: BucketPickerSheetProps): React.JSX.Element {
  const insets = useSafeAreaInsets();

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable testID="bucket-picker-backdrop" style={styles.backdrop} onPress={onClose} />
      <View testID="bucket-picker-sheet" style={[styles.sheet, { paddingBottom: 16 + insets.bottom }]}>
        <View style={styles.grabber} />
        <Text style={styles.heading}>Add to bucket</Text>
        <Text style={styles.track} numberOfLines={2}>
          {trackLabel}
        </Text>
        <ScrollView style={styles.list} contentContainerStyle={styles.listContent}>
          {buckets.map((bucket, index) => (
            <Pressable
              key={bucket.id}
              testID={`bucket-option-${index}`}
              style={({ pressed }) => [styles.option, pressed && styles.optionPressed]}
              onPress={() => onPick(bucket)}
            >
              <Text style={styles.optionEmoji}>{bucket.emoji_id ?? '📁'}</Text>
              <Text style={styles.optionName} numberOfLines={1}>
                {bucket.name}
              </Text>
              <Text style={styles.optionCount}>{bucket.track_ids.length}</Text>
            </Pressable>
          ))}
        </ScrollView>
        <Pressable testID="bucket-picker-cancel" style={styles.cancel} onPress={onClose}>
          <Text style={styles.cancelText}>Cancel</Text>
        </Pressable>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
  },
  sheet: {
    backgroundColor: '#1E1E1E',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 16,
    paddingTop: 8,
    maxHeight: '75%',
  },
  grabber: {
    alignSelf: 'center',
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#444',
    marginBottom: 12,
  },
  heading: {
    color: '#9E9E9E',
    fontSize: 12,
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  track: {
    color: '#E0E0E0',
    fontSize: 16,
    fontWeight: '600',
    marginTop: 4,
    marginBottom: 12,
  },
  list: {
    flexGrow: 0,
  },
  listContent: {
    gap: 8,
  },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    minHeight: 56,
    paddingHorizontal: 16,
    borderRadius: 12,
    backgroundColor: '#2A2A2A',
  },
  optionPressed: {
    backgroundColor: '#3A2F5A',
  },
  optionEmoji: {
    fontSize: 22,
  },
  optionName: {
    flex: 1,
    color: '#E0E0E0',
    fontSize: 16,
    fontWeight: '600',
  },
  optionCount: {
    color: '#9E9E9E',
    fontSize: 13,
    fontFamily: 'monospace',
  },
  cancel: {
    marginTop: 12,
    minHeight: 48,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cancelText: {
    color: '#9E9E9E',
    fontSize: 15,
  },
});
