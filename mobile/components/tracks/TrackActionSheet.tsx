/**
 * Bottom sheet opened by long-pressing a track row. Shows the track, then
 * one 56dp row per action. Back, a scrim tap or picking an action closes it.
 */
import type { ReactElement } from 'react';
import { ActivityIndicator, Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Play, UserRound } from 'lucide-react-native';
import type { LucideIcon } from 'lucide-react-native';
import type { Track } from '@music-minion/shared';
import { trackActions, trackRowSubtitle } from '../../features/home/trackRow';
import type { TrackAction, TrackActionKey } from '../../features/home/trackRow';
import { TrackArtwork } from './TrackArtwork';

const ICONS: Record<TrackActionKey, LucideIcon> = { play: Play, artist: UserRound };

interface TrackActionSheetProps {
  track: Track | null;
  busyKey: TrackActionKey | null;
  onSelect: (key: TrackActionKey) => void;
  onClose: () => void;
}

export function TrackActionSheet({ track, busyKey, onSelect, onClose }: TrackActionSheetProps): ReactElement {
  const { bottom } = useSafeAreaInsets();
  return (
    <Modal visible={track !== null} transparent animationType="fade" onRequestClose={onClose} statusBarTranslucent>
      <Pressable style={styles.scrim} onPress={onClose} accessibilityLabel="Close actions" />
      {track ? (
        <View style={[styles.sheet, { paddingBottom: bottom + 8 }]} testID="track-action-sheet">
          <View style={styles.grabber} />
          <SheetHeader track={track} />
          {trackActions(track).map((action) => (
            <ActionRow key={action.key} action={action} busy={busyKey === action.key} onPress={() => onSelect(action.key)} />
          ))}
        </View>
      ) : null}
    </Modal>
  );
}

function SheetHeader({ track }: { track: Track }): ReactElement {
  return (
    <View style={styles.header}>
      <TrackArtwork trackId={track.id} size={52} />
      <View style={styles.headerText}>
        <Text style={styles.title} numberOfLines={2}>{track.title}</Text>
        <Text style={styles.subtitle} numberOfLines={1}>{trackRowSubtitle(track)}</Text>
      </View>
    </View>
  );
}

function ActionRow({ action, busy, onPress }: { action: TrackAction; busy: boolean; onPress: () => void }): ReactElement {
  const Icon = ICONS[action.key];
  return (
    <Pressable
      testID={`track-action-${action.key}`}
      style={styles.action}
      onPress={onPress}
      disabled={busy}
      accessibilityRole="button"
      android_ripple={{ color: '#FFFFFF14' }}
    >
      <Icon size={22} color="#E0E0E0" />
      <Text style={styles.actionLabel}>{action.label}</Text>
      {busy ? <ActivityIndicator size="small" color="#7C4DFF" /> : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  scrim: { flex: 1, backgroundColor: '#00000099' },
  sheet: {
    backgroundColor: '#1A1A1A',
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    paddingTop: 8,
  },
  grabber: {
    alignSelf: 'center',
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: '#3A3A3A',
    marginBottom: 8,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 14,
    paddingHorizontal: 20,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#2E2E2E',
    marginBottom: 4,
  },
  headerText: { flex: 1 },
  title: { color: '#E0E0E0', fontSize: 16, fontWeight: '600' },
  subtitle: { color: '#9E9E9E', fontSize: 13, marginTop: 2 },
  action: {
    flexDirection: 'row',
    alignItems: 'center',
    height: 56,
    paddingHorizontal: 20,
    gap: 18,
  },
  actionLabel: { flex: 1, color: '#E0E0E0', fontSize: 16 },
});
