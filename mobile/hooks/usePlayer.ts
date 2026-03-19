/**
 * Mobile player hook — bridges RNTP with shared playerStore.
 *
 * Responsibilities:
 * - RNTP setup (capabilities, queue management)
 * - Track loading when store.currentTrack changes
 * - Scrobble tracking (50% or 30s threshold)
 * - Auto-advance on track end
 * - Error handling with auto-skip
 */
import { useEffect, useRef } from 'react';
import TrackPlayer, {
  Capability,
  Event,
  useTrackPlayerEvents,
  useProgress,
  usePlaybackState,
} from 'react-native-track-player';
import { usePlayerStore, getCurrentPosition } from '../stores/playerStore';
import { getStreamUrl } from '@music-minion/shared';

let isSetup = false;

async function setupPlayer(): Promise<void> {
  if (isSetup) return;
  try {
    await TrackPlayer.setupPlayer({
      // Buffer config for streaming over Tailscale
      minBuffer: 15,
      maxBuffer: 50,
      playBuffer: 2,
      backBuffer: 5,
    });
    await TrackPlayer.updateOptions({
      capabilities: [
        Capability.Play,
        Capability.Pause,
        Capability.SkipToNext,
        Capability.SkipToPrevious,
        Capability.SeekTo,
        Capability.Stop,
      ],
      compactCapabilities: [
        Capability.Play,
        Capability.Pause,
        Capability.SkipToNext,
      ],
      // Android notification
      android: {
        appKilledPlaybackBehavior: 'StopPlaybackAndRemoveNotification',
      },
    });
    isSetup = true;
  } catch (err) {
    // Already set up — RNTP throws if called twice
    if ((err as Error).message?.includes('already been initialized')) {
      isSetup = true;
    }
  }
}

export function usePlayer() {
  const store = usePlayerStore();
  const { position } = useProgress(250); // Update every 250ms
  const playbackState = usePlaybackState();
  const lastLoadedTrackIdRef = useRef<number | null>(null);
  const scrobbleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Setup RNTP on mount
  useEffect(() => {
    setupPlayer();
  }, []);

  // Load track into RNTP when currentTrack changes and this device is active
  useEffect(() => {
    if (!store.isThisDeviceActive || !store.currentTrack) return;
    if (!isSetup) return;
    if (lastLoadedTrackIdRef.current === store.currentTrack.id) return;

    const track = store.currentTrack;
    lastLoadedTrackIdRef.current = track.id;

    const loadTrack = async () => {
      try {
        await TrackPlayer.reset();
        await TrackPlayer.add({
          id: track.id.toString(),
          url: getStreamUrl(track.id),
          title: track.title,
          artist: track.artist ?? 'Unknown Artist',
          duration: track.duration,
        });

        // Seek to current position if resuming mid-track
        const pos = getCurrentPosition(store) / 1000;
        if (pos > 1) {
          await TrackPlayer.seekTo(pos);
        }

        if (store.isPlaying) {
          await TrackPlayer.play();
        }
      } catch (err) {
        store.setPlaybackError(
          err instanceof Error ? err.message : 'Failed to load track'
        );
      }
    };

    loadTrack();
  }, [store.currentTrack?.id, store.isThisDeviceActive]);

  // Play/pause sync
  useEffect(() => {
    if (!store.isThisDeviceActive || !store.currentTrack || !isSetup) return;

    if (store.isPlaying) {
      TrackPlayer.play();
    } else {
      TrackPlayer.pause();
    }
  }, [store.isPlaying, store.isThisDeviceActive]);

  // Pause when device becomes inactive
  useEffect(() => {
    if (!store.isThisDeviceActive && isSetup) {
      TrackPlayer.pause();
    }
  }, [store.isThisDeviceActive]);

  // Scrobble tracking
  useEffect(() => {
    if (!store.isPlaying || !store.isThisDeviceActive || !store.currentTrack) return;
    if (store.scrobbledThisPlaythrough) return;

    const duration = (store.currentTrack.duration ?? 0) * 1000;
    const threshold = Math.min(duration * 0.5, 30000);
    const currentPos = getCurrentPosition(store);
    const remaining = threshold - currentPos;

    if (remaining <= 0) {
      store.onTrackPlayed(store.currentTrack.id, currentPos);
      return;
    }

    scrobbleTimerRef.current = setTimeout(() => {
      const pos = getCurrentPosition(usePlayerStore.getState());
      const trackId = usePlayerStore.getState().currentTrack?.id;
      if (trackId && !usePlayerStore.getState().scrobbledThisPlaythrough) {
        usePlayerStore.getState().onTrackPlayed(trackId, pos);
      }
    }, remaining);

    return () => {
      if (scrobbleTimerRef.current) clearTimeout(scrobbleTimerRef.current);
    };
  }, [store.currentTrack?.id, store.isPlaying, store.scrobbledThisPlaythrough]);

  // Handle track end — auto-advance
  useTrackPlayerEvents([Event.PlaybackQueueEnded], () => {
    const state = usePlayerStore.getState();
    if (state.currentContext?.type === 'comparison') return;
    state.next();
  });

  // Handle playback error — auto-skip after 2s
  useTrackPlayerEvents([Event.PlaybackError], () => {
    const trackTitle = usePlayerStore.getState().currentTrack?.title ?? 'Unknown';
    usePlayerStore.getState().setPlaybackError(`Failed to load: ${trackTitle}`);
    setTimeout(() => usePlayerStore.getState().next(), 2000);
  });

  return {
    ...store,
    /** RNTP position in seconds (for seek slider) */
    rntpPosition: position,
    /** RNTP playback state */
    rntpState: playbackState,
    /** Whether RNTP is initialized */
    isPlayerReady: isSetup,
  };
}
