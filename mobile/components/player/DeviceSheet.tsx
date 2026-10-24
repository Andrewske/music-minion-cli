/**
 * Device sheet — where playback is and where it can go.
 *
 *   ───
 *   Playing on Kevin laptop
 *   [ ▯ Play here            Android Phone ]   ← large, first
 *   Other devices
 *   ⊡ Kevin laptop                 ♪ Playing
 *   ⊡ Living room
 *
 * Transfers use the shared store's setActiveDevice (POST /player/transfer).
 * "Play here" is only reachable from this sheet, never from the bar itself,
 * so a stray tap can't pull playback onto the phone.
 */
import type { ReactElement } from 'react';
import { Modal, View, Text, Pressable, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import { Check, MonitorSpeaker, Smartphone, Volume2 } from 'lucide-react-native';
import { usePlayerStore } from '../../stores/playerStore';
import { activeDeviceName, otherDeviceRows } from '../../features/player/devices';
import type { DeviceRow } from '../../features/player/devices';

interface DeviceSheetProps {
  visible: boolean;
  onClose: () => void;
}

export function DeviceSheet({ visible, onClose }: DeviceSheetProps): ReactElement {
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose} statusBarTranslucent>
      <Pressable testID="device-sheet-scrim" style={styles.scrim} onPress={onClose} accessibilityLabel="Close devices" />
      <View testID="device-sheet" style={[styles.sheet, { paddingBottom: 20 + insets.bottom }]}>
        <View style={styles.handle} />
        <DeviceSheetBody onClose={onClose} />
      </View>
    </Modal>
  );
}

function DeviceSheetBody({ onClose }: { onClose: () => void }): ReactElement {
  const devices = usePlayerStore((s) => s.availableDevices);
  const activeDeviceId = usePlayerStore((s) => s.activeDeviceId);
  const thisDeviceId = usePlayerStore((s) => s.thisDeviceId);
  const isHere = usePlayerStore((s) => s.isThisDeviceActive);
  const setActiveDevice = usePlayerStore((s) => s.setActiveDevice);
  const rows = otherDeviceRows(devices, thisDeviceId, activeDeviceId);

  const transfer = (deviceId: string): void => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    void setActiveDevice(deviceId);
    onClose();
  };

  return (
    <>
      <Text style={styles.title} numberOfLines={1}>
        {isHere ? 'Playing on this phone' : `Playing on ${activeDeviceName(devices, activeDeviceId)}`}
      </Text>
      <PlayHereButton isHere={isHere} onPress={() => transfer(thisDeviceId)} />
      <Text style={styles.sectionLabel}>Other devices</Text>
      {rows.length === 0 ? (
        <Text style={styles.empty}>No other devices are connected. Open Music Minion on another device to send playback there.</Text>
      ) : (
        rows.map((row) => <DeviceListRow key={row.id} row={row} onPress={() => transfer(row.id)} />)
      )}
    </>
  );
}

function PlayHereButton({ isHere, onPress }: { isHere: boolean; onPress: () => void }): ReactElement {
  const thisDeviceName = usePlayerStore((s) => s.thisDeviceName);
  const Icon = isHere ? Check : Smartphone;
  return (
    <Pressable
      testID="device-play-here"
      accessibilityRole="button"
      accessibilityLabel={isHere ? 'Already playing here' : 'Play here'}
      accessibilityState={{ disabled: isHere }}
      disabled={isHere}
      onPress={onPress}
      android_ripple={{ color: '#FFFFFF33' }}
      style={[styles.playHere, isHere && styles.playHereActive]}
    >
      <Icon size={26} color={isHere ? '#B39DFF' : '#FFFFFF'} strokeWidth={2} />
      <View style={styles.playHereText}>
        <Text style={[styles.playHereLabel, isHere && styles.playHereLabelActive]}>{isHere ? 'Playing here' : 'Play here'}</Text>
        <Text style={[styles.playHereSub, isHere && styles.playHereSubActive]} numberOfLines={1}>{thisDeviceName}</Text>
      </View>
    </Pressable>
  );
}

function DeviceListRow({ row, onPress }: { row: DeviceRow; onPress: () => void }): ReactElement {
  return (
    <Pressable
      testID={`device-row-${row.id}`}
      accessibilityRole="button"
      accessibilityLabel={row.isActive ? `${row.name}, playing now` : `Play on ${row.name}`}
      accessibilityState={{ selected: row.isActive, disabled: row.isActive }}
      disabled={row.isActive}
      onPress={onPress}
      android_ripple={{ color: '#FFFFFF14' }}
      style={styles.row}
    >
      <MonitorSpeaker size={22} color={row.isActive ? '#7C4DFF' : '#9E9E9E'} strokeWidth={1.75} />
      <Text style={[styles.rowName, row.isActive && styles.rowNameActive]} numberOfLines={1}>{row.name}</Text>
      {row.isActive ? (
        <View style={styles.activeTag}>
          <Volume2 size={14} color="#7C4DFF" strokeWidth={2} />
          <Text style={styles.activeTagText}>Playing</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  scrim: { flex: 1, backgroundColor: '#000000A6' },
  sheet: {
    backgroundColor: '#1A1A1A',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 16,
    paddingTop: 8,
  },
  handle: { alignSelf: 'center', width: 36, height: 4, borderRadius: 2, backgroundColor: '#444', marginBottom: 16 },
  title: { color: '#E0E0E0', fontSize: 18, fontWeight: '600', marginBottom: 16, paddingHorizontal: 4 },
  playHere: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
    minHeight: 72,
    paddingHorizontal: 20,
    borderRadius: 16,
    backgroundColor: '#7C4DFF',
    overflow: 'hidden',
  },
  playHereActive: { backgroundColor: '#7C4DFF1F', borderWidth: 1, borderColor: '#7C4DFF66' },
  playHereText: { flex: 1 },
  playHereLabel: { color: '#FFFFFF', fontSize: 18, fontWeight: '700' },
  playHereLabelActive: { color: '#B39DFF' },
  playHereSub: { color: '#FFFFFFB3', fontSize: 13, marginTop: 2 },
  playHereSubActive: { color: '#9E9E9E' },
  sectionLabel: { color: '#9E9E9E', fontSize: 13, fontWeight: '600', marginTop: 24, marginBottom: 4, paddingHorizontal: 4 },
  empty: { color: '#666', fontSize: 14, lineHeight: 20, paddingHorizontal: 4, paddingVertical: 12 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 14, minHeight: 56, paddingHorizontal: 4 },
  rowName: { flex: 1, color: '#E0E0E0', fontSize: 16 },
  rowNameActive: { color: '#B39DFF', fontWeight: '600' },
  activeTag: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  activeTagText: { color: '#7C4DFF', fontSize: 13, fontWeight: '600' },
});
