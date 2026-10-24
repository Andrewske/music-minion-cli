/**
 * Full player — opened from the mini bar as a page sheet.
 *
 *   ───                       (tap to collapse)
 *   [      artwork      ]
 *   Title / artist (or "on <device>", opens the device sheet)
 *   ━━━━━━━━━○──────────  0:42 / 3:10
 *   ✓ Counted as played   (fixed-height slot, no layout shift)
 *        ⏮    (▶)    ⏭
 *   ♡ Like   ≡+ Add   ⊡ Device   ≣ Queue
 *   Up next                 3 / 40 in queue  [⇄]
 *    4  [art] Track · Artist
 *    5  …
 *
 * Like and Add to playlist are disabled: the shared API has no like or
 * add-to-playlist call yet (see PR for #69).
 */
import { useRef, useState } from 'react';
import type { ReactElement } from 'react';
import { View, Text, Pressable, StyleSheet, ScrollView, Platform, useWindowDimensions } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as Haptics from 'expo-haptics';
import { Check, MonitorSpeaker, Pause, Play, SkipBack, SkipForward } from 'lucide-react-native';
import type { Track } from '@music-minion/shared';
import { usePlayer } from '../../hooks/usePlayer';
import { usePlayerStore } from '../../stores/playerStore';
import { SeekSlider } from './SeekSlider';
import { armBadStream, E2E_ENABLED } from '../../services/e2eHooks';
import { PlaybackErrorBanner } from './PlaybackErrorBanner';
import { DeviceSheet } from './DeviceSheet';
import { TrackArtwork } from './TrackArtwork';
import { PlayerActionRow } from './PlayerActionRow';
import { UpNextList } from './UpNextList';
import { usePlaybackPosition } from './usePlaybackPosition';
import { playerSecondLine } from '../../features/player/devices';
import { fullPlayerInsets } from '../../features/player/sheetInsets';

interface NowPlayingProps {
  onCollapse: () => void;
}

const haptic = (style: Haptics.ImpactFeedbackStyle): void => {
  Haptics.impactAsync(style);
};

export function NowPlaying({ onCollapse }: NowPlayingProps): ReactElement | null {
  const player = usePlayer();
  const [devicesOpen, setDevicesOpen] = useState(false);
  const scrollRef = useRef<ScrollView>(null);
  const upNextY = useRef(0);
  const position = usePlaybackPosition(player.rntpPosition);
  // A Modal is its own window: the root layout's safe-area padding stops here.
  const pad = fullPlayerInsets(Platform.OS, useSafeAreaInsets());
  const track = player.currentTrack;
  if (!track) return null;

  // seek() POSTs and sets lastSeekAt; usePlayer's lastSeekAt effect applies
  // TrackPlayer.seekTo. Seeking locally here too would double-apply.
  const handleSeek = (seconds: number): void => void player.seek(seconds * 1000);
  const openDevices = (): void => setDevicesOpen(true);
  const showQueue = (): void => scrollRef.current?.scrollTo({ y: upNextY.current, animated: true });

  return (
    <View testID="now-playing" style={[styles.container, { paddingTop: pad.top }]}>
      <ScrollView ref={scrollRef} style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: 48 + pad.bottom }]}>
        <Pressable style={styles.handleArea} onPress={onCollapse} accessibilityLabel="Close player">
          <View style={styles.handle} />
        </Pressable>
        <View style={styles.bannerWrap}><PlaybackErrorBanner /></View>
        <Hero track={track} onDevices={openDevices} />
        <SeekSlider position={position} duration={track.duration ?? 0} onSeek={handleSeek} />
        <ScrobbledSlot visible={player.scrobbledThisPlaythrough} />
        <Transport isPlaying={player.isPlaying} onPlayPause={player.isPlaying ? player.pause : player.resume} onPrev={player.prev} onNext={player.next} />
        <PlayerActionRow onDevices={openDevices} onQueue={showQueue} />
        <View style={styles.fullWidth} onLayout={(e) => { upNextY.current = e.nativeEvent.layout.y; }}>
          <UpNextList />
        </View>
      </ScrollView>
      <DeviceSheet visible={devicesOpen} onClose={() => setDevicesOpen(false)} />
    </View>
  );
}

function Hero({ track, onDevices }: { track: Track; onDevices: () => void }): ReactElement {
  const { width } = useWindowDimensions();
  const isThisDeviceActive = usePlayerStore((s) => s.isThisDeviceActive);
  const devices = usePlayerStore((s) => s.availableDevices);
  const activeDeviceId = usePlayerStore((s) => s.activeDeviceId);
  const line = playerSecondLine({ isThisDeviceActive, artist: track.artist, devices, activeDeviceId });
  const artSize = Math.min(width - 112, 264);
  return (
    <>
      <View style={styles.art}>
        <TrackArtwork trackId={track.id} size={artSize} radius={14} label={`Artwork for ${track.title}`} />
      </View>
      <Text testID="now-playing-title" style={styles.title} numberOfLines={2} onLongPress={E2E_ENABLED ? armBadStream : undefined}>
        {track.title}
      </Text>
      <Text style={styles.artist} numberOfLines={1}>{track.artist ?? 'Unknown Artist'}</Text>
      {line.isRemote ? <RemoteDeviceChip text={line.text} onPress={onDevices} /> : null}
    </>
  );
}

function RemoteDeviceChip({ text, onPress }: { text: string; onPress: () => void }): ReactElement {
  return (
    <Pressable
      testID="now-playing-device-line"
      accessibilityRole="button"
      accessibilityLabel={`Playing ${text}. Choose device`}
      onPress={onPress}
      android_ripple={{ color: '#7C4DFF33' }}
      style={styles.remoteChip}
    >
      <MonitorSpeaker size={14} color="#7C4DFF" strokeWidth={2.25} />
      <Text style={styles.remoteText} numberOfLines={1}>{text}</Text>
    </Pressable>
  );
}

function ScrobbledSlot({ visible }: { visible: boolean }): ReactElement {
  return (
    <View style={styles.scrobbledSlot}>
      {visible ? (
        <View testID="now-playing-scrobbled" style={styles.scrobbled}>
          <Check size={13} color="#666" strokeWidth={2.5} />
          <Text style={styles.scrobbledText}>Counted as played</Text>
        </View>
      ) : null}
    </View>
  );
}

interface TransportProps {
  isPlaying: boolean;
  onPlayPause: () => Promise<void>;
  onPrev: () => Promise<void>;
  onNext: () => Promise<void>;
}

function Transport({ isPlaying, onPlayPause, onPrev, onNext }: TransportProps): ReactElement {
  const PlayIcon = isPlaying ? Pause : Play;
  const press = (fn: () => Promise<void>, style: Haptics.ImpactFeedbackStyle): (() => void) => (): void => {
    haptic(style);
    void fn();
  };
  const ripple = { color: '#FFFFFF1F', borderless: true, radius: 28 };
  return (
    <View style={styles.transport}>
      <Pressable testID="now-playing-prev" accessibilityRole="button" accessibilityLabel="Previous track" style={styles.skipBtn} android_ripple={ripple} onPress={press(onPrev, Haptics.ImpactFeedbackStyle.Light)}>
        <SkipBack size={30} color="#E0E0E0" fill="#E0E0E0" strokeWidth={1.75} />
      </Pressable>
      <Pressable testID="now-playing-play-pause" accessibilityRole="button" accessibilityLabel={isPlaying ? 'Pause' : 'Play'} style={styles.playBtn} android_ripple={{ ...ripple, color: '#FFFFFF33', radius: 36 }} onPress={press(onPlayPause, Haptics.ImpactFeedbackStyle.Medium)}>
        <PlayIcon size={30} color="#FFFFFF" fill="#FFFFFF" strokeWidth={1.75} />
      </Pressable>
      <Pressable testID="now-playing-next" accessibilityRole="button" accessibilityLabel="Next track" style={styles.skipBtn} android_ripple={ripple} onPress={press(onNext, Haptics.ImpactFeedbackStyle.Light)}>
        <SkipForward size={30} color="#E0E0E0" fill="#E0E0E0" strokeWidth={1.75} />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#121212' },
  // paddingBottom is set inline: 48 + the navigation bar inset
  content: { alignItems: 'center', paddingHorizontal: 20 },
  handleArea: { width: '100%', alignItems: 'center', paddingVertical: 12 },
  handle: { width: 40, height: 4, borderRadius: 2, backgroundColor: '#555' },
  // Parent content container centers children; these must span full width
  bannerWrap: { width: '100%' },
  fullWidth: { width: '100%' },
  art: { marginTop: 12, marginBottom: 20 },
  title: {
    color: '#E0E0E0',
    fontSize: 22,
    fontWeight: '700',
    textAlign: 'center',
    paddingHorizontal: 12,
    marginBottom: 4,
  },
  artist: { color: '#9E9E9E', fontSize: 16, textAlign: 'center' },
  remoteChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 10,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 14,
    backgroundColor: '#7C4DFF1F',
    overflow: 'hidden',
    maxWidth: '100%',
  },
  remoteText: { color: '#B39DFF', fontSize: 13, fontWeight: '600', flexShrink: 1 },
  scrobbledSlot: { height: 18, marginTop: 4, justifyContent: 'center' },
  scrobbled: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  scrobbledText: { color: '#666', fontSize: 12 },
  transport: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 28,
    marginTop: 8,
    marginBottom: 20,
  },
  skipBtn: { width: 56, height: 56, alignItems: 'center', justifyContent: 'center' },
  playBtn: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: '#7C4DFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
