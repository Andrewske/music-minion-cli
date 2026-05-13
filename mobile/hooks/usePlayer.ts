import { useEffect, useRef } from 'react';
import TrackPlayer, {
  Event,
  PlayerCommand,
  useProgress,
  usePlaybackState,
  PlaybackState,
} from '@rntp/player';
import { usePlayerStore, getCurrentPosition } from '../stores/playerStore';
import { getStreamUrl } from '@music-minion/shared';

let isSetup = false;

function setupPlayer(): void {
  if (isSetup) return;
  try {
    TrackPlayer.setupPlayer({
      contentType: 'music',
    });
    TrackPlayer.setCommands({
      capabilities: [
        PlayerCommand.PlayPause,
        PlayerCommand.Next,
        PlayerCommand.Previous,
        PlayerCommand.Seek,
        PlayerCommand.Stop,
      ],
      handling: 'native',
    });
    isSetup = true;
  } catch {
    isSetup = true;
  }
}

export function usePlayer() {
  const store = usePlayerStore();
  const { position } = useProgress(0.25);
  const playbackState = usePlaybackState();
  const lastLoadedTrackIdRef = useRef<number | null>(null);
  const scrobbleTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

    const loadTrack = (): void => {
      try {
        TrackPlayer.setMediaItem({
          mediaId: track.id.toString(),
          url: getStreamUrl(track.id),
          title: track.title,
          artist: track.artist ?? 'Unknown Artist',
          duration: track.duration,
        });

        const pos = getCurrentPosition(store) / 1000;
        if (pos > 1) {
          TrackPlayer.seekTo(pos);
        }

        if (store.isPlaying) {
          TrackPlayer.play();
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

  // Handle track end + playback errors via addEventListener (v5 removed useTrackPlayerEvents)
  useEffect(() => {
    const stateListener = TrackPlayer.addEventListener(
      Event.PlaybackStateChanged,
      (event) => {
        if (event.state === PlaybackState.Ended) {
          const state = usePlayerStore.getState();
          if (state.currentContext?.type !== 'comparison') {
            state.next();
          }
        }
      }
    );

    const errorListener = TrackPlayer.addEventListener(
      Event.PlaybackError,
      () => {
        const trackTitle = usePlayerStore.getState().currentTrack?.title ?? 'Unknown';
        usePlayerStore.getState().setPlaybackError(`Failed to load: ${trackTitle}`);
        setTimeout(() => usePlayerStore.getState().next(), 2000);
      }
    );

    return () => {
      stateListener.remove();
      errorListener.remove();
    };
  }, []);

  return {
    ...store,
    rntpPosition: position,
    rntpState: playbackState,
    isPlayerReady: isSetup,
  };
}
