/**
 * Up next: the next tracks in the player queue, numbered by queue position.
 * The header carries the queue position (`now-playing-queue-info`, parsed by
 * Maestro flows) and the shuffle toggle, since shuffle reorders this list.
 */
import { memo } from 'react';
import type { ReactElement } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import * as Haptics from 'expo-haptics';
import { Shuffle } from 'lucide-react-native';
import { usePlayerStore } from '../../stores/playerStore';
import { TrackArtwork } from './TrackArtwork';
import { queueInfoLabel, upNextSlice } from '../../features/player/upNext';
import type { UpNextRow } from '../../features/player/upNext';

export function UpNextList(): ReactElement {
  const queue = usePlayerStore((s) => s.queue);
  const queueIndex = usePlayerStore((s) => s.queueIndex);
  const { rows, remaining } = upNextSlice(queue, queueIndex);
  return (
    <View testID="now-playing-up-next" style={styles.section}>
      <UpNextHeader label={queueInfoLabel(queueIndex, queue.length)} />
      {rows.length === 0 ? <Text style={styles.empty}>Nothing queued after this track.</Text> : null}
      {rows.map((row) => <UpNextItem key={`${row.position}-${row.track.id}`} row={row} />)}
      {remaining > 0 ? <Text style={styles.more}>{remaining} more after these</Text> : null}
    </View>
  );
}

function UpNextHeader({ label }: { label: string }): ReactElement {
  const shuffleEnabled = usePlayerStore((s) => s.shuffleEnabled);
  const toggleShuffleSmooth = usePlayerStore((s) => s.toggleShuffleSmooth);
  const handleShuffle = (): void => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    void toggleShuffleSmooth();
  };
  return (
    <View style={styles.header}>
      <Text style={styles.heading} accessibilityRole="header">Up next</Text>
      <Text testID="now-playing-queue-info" style={styles.queueInfo}>{label}</Text>
      <Pressable
        testID="now-playing-shuffle"
        accessibilityRole="switch"
        accessibilityLabel="Shuffle"
        accessibilityState={{ checked: shuffleEnabled }}
        onPress={handleShuffle}
        android_ripple={{ color: '#FFFFFF1F', borderless: true, radius: 22 }}
        style={[styles.shuffle, shuffleEnabled && styles.shuffleOn]}
      >
        <Shuffle size={18} color={shuffleEnabled ? '#7C4DFF' : '#9E9E9E'} strokeWidth={2} />
      </Pressable>
    </View>
  );
}

const UpNextItem = memo(function UpNextItem({ row }: { row: UpNextRow }): ReactElement {
  return (
    <View style={styles.item}>
      <Text style={styles.position}>{row.position}</Text>
      <TrackArtwork trackId={row.track.id} size={40} radius={4} />
      <View style={styles.itemText}>
        <Text style={styles.itemTitle} numberOfLines={1}>{row.track.title}</Text>
        <Text style={styles.itemArtist} numberOfLines={1}>{row.track.artist ?? 'Unknown Artist'}</Text>
      </View>
    </View>
  );
});

const styles = StyleSheet.create({
  section: { width: '100%', borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: '#2A2A2A', paddingTop: 8 },
  header: { flexDirection: 'row', alignItems: 'center', minHeight: 48 },
  heading: { flex: 1, color: '#E0E0E0', fontSize: 16, fontWeight: '600' },
  queueInfo: { color: '#666', fontSize: 12, fontVariant: ['tabular-nums'], marginRight: 8 },
  shuffle: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' },
  shuffleOn: { backgroundColor: '#7C4DFF26' },
  empty: { color: '#666', fontSize: 14, paddingVertical: 12 },
  item: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56 },
  position: { width: 24, color: '#666', fontSize: 12, textAlign: 'right', fontVariant: ['tabular-nums'] },
  itemText: { flex: 1 },
  itemTitle: { color: '#E0E0E0', fontSize: 14 },
  itemArtist: { color: '#9E9E9E', fontSize: 12, marginTop: 2 },
  more: { color: '#666', fontSize: 12, paddingVertical: 12, paddingLeft: 36 },
});
