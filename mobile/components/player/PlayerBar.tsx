/**
 * Mini player bar — persistent at the bottom of every screen.
 *
 *   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 2px progress
 *   [art]  Title                                   (▶)  ⏭
 *          Artist
 *          ⊡ on Kevin laptop      (remote only: opens device sheet)
 *
 * The whole artwork/title/artist row opens the full player (NowPlaying).
 * When another device is playing, a compact chip in its own row below names
 * it and opens the device sheet. It used to be the second text line inside
 * the expand area, and its hitSlop reached the row's vertical center, so a
 * tap in the middle of the bar opened the sheet. ⏮ lives in the full
 * player only.
 */
import { useState } from 'react';
import type { ReactElement } from 'react';
import { View, Text, Pressable, StyleSheet, Modal } from 'react-native';
import * as Haptics from 'expo-haptics';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { MonitorSpeaker, Pause, Play, SkipForward } from 'lucide-react-native';
import type { Track } from '@music-minion/shared';
import { usePlayer } from '../../hooks/usePlayer';
import { usePlayerStore } from '../../stores/playerStore';
import { NowPlaying } from './NowPlaying';
import { PlaybackErrorBanner } from './PlaybackErrorBanner';
import { DeviceSheet } from './DeviceSheet';
import { TrackArtwork } from './TrackArtwork';
import { usePlaybackPosition } from './usePlaybackPosition';
import { playerSecondLine } from '../../features/player/devices';
import { progressFraction } from '../../features/player/progress';

const tap = (): void => {
  Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
};

export function PlayerBar(): ReactElement {
  const insets = useSafeAreaInsets();
  const [expanded, setExpanded] = useState(false);
  const [devicesOpen, setDevicesOpen] = useState(false);
  const player = usePlayer();
  const bottomPad = { paddingBottom: 8 + insets.bottom };

  if (!player.currentTrack) return <EmptyBar style={bottomPad} />;

  const withTap = (fn: () => unknown): (() => void) => (): void => {
    tap();
    fn();
  };
  const playPause = (): Promise<void> => (player.isPlaying ? player.pause() : player.resume());

  return (
    <>
      <PlaybackErrorBanner />
      <View testID="player-bar" style={[styles.bar, bottomPad]}>
        <ProgressLine track={player.currentTrack} localPositionSec={player.rntpPosition} />
        <View style={styles.row}>
          <BarInfo track={player.currentTrack} onExpand={withTap(() => setExpanded(true))} />
          <BarControls isPlaying={player.isPlaying} onPlayPause={withTap(playPause)} onNext={withTap(player.next)} />
        </View>
        <DeviceChip artist={player.currentTrack.artist} onPress={withTap(() => setDevicesOpen(true))} />
      </View>
      {/* Edge-to-edge on Android; NowPlaying pads itself by the system bar insets */}
      <Modal
        visible={expanded}
        animationType="slide"
        presentationStyle="pageSheet"
        statusBarTranslucent
        navigationBarTranslucent
        onRequestClose={() => setExpanded(false)}
      >
        <NowPlaying onCollapse={() => setExpanded(false)} />
      </Modal>
      <DeviceSheet visible={devicesOpen} onClose={() => setDevicesOpen(false)} />
    </>
  );
}

function EmptyBar({ style }: { style: { paddingBottom: number } }): ReactElement {
  return (
    <>
      {/* Play/control POSTs can fail before any track loads (offline) */}
      <PlaybackErrorBanner />
      <View style={[styles.barEmpty, style]}>
        <Text style={styles.emptyText}>Nothing playing</Text>
      </View>
    </>
  );
}

function ProgressLine({ track, localPositionSec }: { track: Track; localPositionSec: number }): ReactElement {
  const position = usePlaybackPosition(localPositionSec);
  const fraction = progressFraction(position, track.duration);
  return (
    <View testID="player-bar-progress" style={styles.progressTrack} pointerEvents="none">
      <View style={[styles.progressFill, { width: `${fraction * 100}%` }]} />
    </View>
  );
}

interface BarInfoProps {
  track: Track;
  onExpand: () => void;
}

/** Artwork + title + artist: one tap target that opens the full player. */
function BarInfo({ track, onExpand }: BarInfoProps): ReactElement {
  return (
    <Pressable testID="player-bar-expand" accessibilityLabel="Open player" style={styles.info} onPress={onExpand}>
      <TrackArtwork trackId={track.id} size={44} radius={6} />
      <View style={styles.text}>
        <Text testID="player-track-title" style={styles.title} numberOfLines={1}>{track.title}</Text>
        <Text style={styles.artist} numberOfLines={1}>{track.artist ?? 'Unknown Artist'}</Text>
      </View>
    </Pressable>
  );
}

/**
 * "⊡ on <device>" chip, only while another device plays. It sits in its own
 * row below the expand area (not inside it), and its hitSlop never reaches up
 * into that row, so the two tap targets can't overlap.
 */
function DeviceChip({ artist, onPress }: { artist: string | undefined; onPress: () => void }): ReactElement | null {
  // Store selectors, not usePlayer(): every usePlayer() mount adds RNTP effects.
  const isThisDeviceActive = usePlayerStore((s) => s.isThisDeviceActive);
  const devices = usePlayerStore((s) => s.availableDevices);
  const activeDeviceId = usePlayerStore((s) => s.activeDeviceId);
  const line = playerSecondLine({ isThisDeviceActive, artist, devices, activeDeviceId });
  if (!line.isRemote) return null;
  return (
    <Pressable
      testID="player-device-line"
      accessibilityRole="button"
      accessibilityLabel={`Playing ${line.text}. Choose device`}
      onPress={onPress}
      hitSlop={{ top: 0, bottom: 6, left: 8, right: 8 }}
      android_ripple={{ color: '#7C4DFF33' }}
      style={styles.deviceChip}
    >
      <MonitorSpeaker size={12} color="#B39DFF" strokeWidth={2.25} />
      <Text style={styles.deviceText} numberOfLines={1}>{line.text}</Text>
    </Pressable>
  );
}

interface BarControlsProps {
  isPlaying: boolean;
  onPlayPause: () => void;
  onNext: () => void;
}

function BarControls({ isPlaying, onPlayPause, onNext }: BarControlsProps): ReactElement {
  const PlayIcon = isPlaying ? Pause : Play;
  return (
    <View style={styles.controls}>
      <Pressable
        testID="player-play-pause"
        accessibilityRole="button"
        accessibilityLabel={isPlaying ? 'Pause' : 'Play'}
        style={styles.playBtn}
        onPress={onPlayPause}
        android_ripple={{ color: '#FFFFFF33', borderless: true, radius: 22 }}
        hitSlop={6}
      >
        <PlayIcon size={20} color="#FFFFFF" fill="#FFFFFF" strokeWidth={2} />
      </Pressable>
      <Pressable
        testID="player-next"
        accessibilityRole="button"
        accessibilityLabel="Next track"
        style={styles.nextBtn}
        onPress={onNext}
        android_ripple={{ color: '#FFFFFF1F', borderless: true, radius: 22 }}
      >
        <SkipForward size={22} color="#E0E0E0" fill="#E0E0E0" strokeWidth={2} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    backgroundColor: '#1A1A1A',
    paddingLeft: 10,
    paddingRight: 6,
    paddingTop: 10,
  },
  barEmpty: {
    backgroundColor: '#1A1A1A',
    borderTopWidth: 1,
    borderTopColor: '#2A2A2A',
    paddingHorizontal: 16,
    paddingTop: 10,
    justifyContent: 'center',
  },
  emptyText: { color: '#555', fontSize: 13 },
  progressTrack: { position: 'absolute', top: 0, left: 0, right: 0, height: 2, backgroundColor: '#2A2A2A' },
  progressFill: { height: 2, backgroundColor: '#7C4DFF' },
  row: { flexDirection: 'row', alignItems: 'center' },
  info: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12, marginRight: 4 },
  text: { flex: 1 },
  title: { color: '#E0E0E0', fontSize: 14, fontWeight: '600' },
  artist: { color: '#9E9E9E', fontSize: 12, marginTop: 2 },
  // Text lines up with the title: 44 artwork + 12 gap - 8 chip padding
  deviceChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    alignSelf: 'flex-start',
    maxWidth: '70%',
    marginLeft: 48,
    marginTop: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 10,
    backgroundColor: '#7C4DFF1F',
    overflow: 'hidden',
  },
  deviceText: { color: '#B39DFF', fontSize: 12, fontWeight: '600', flexShrink: 1 },
  controls: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  playBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#7C4DFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  nextBtn: { width: 48, height: 48, alignItems: 'center', justifyContent: 'center' },
});
