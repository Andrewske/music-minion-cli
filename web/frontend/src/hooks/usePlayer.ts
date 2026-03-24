import { useEffect, useRef, useCallback } from 'react';
import { usePlayerStore, getCurrentPosition } from '../stores/playerStore';
import { useAudioElement } from '../contexts/AudioElementContext';

export function usePlayer() {
  const store = usePlayerStore();
  const audio = useAudioElement();
  const lastLoadedTrackIdRef = useRef<number | null>(null);

  // Initialize device on mount
  useEffect(() => {
    store.registerDevice();
  }, [store]);

  // Initialize audio volume/mute when audio becomes available
  useEffect(() => {
    if (!audio) return;
    audio.volume = store.volume;
    audio.muted = store.isMuted;
  }, [audio]);

  // Update volume when store changes
  useEffect(() => {
    if (!audio) return;
    audio.volume = store.volume;
  }, [audio, store.volume]);

  // Update mute when store changes
  useEffect(() => {
    if (!audio) return;
    audio.muted = store.isMuted;
  }, [audio, store.isMuted]);

  const handlePlayError = useCallback((err: Error) => {
    if (err.name === 'NotAllowedError') {
      store.set({ needsUserGesture: true });
    } else if (err.name !== 'AbortError') {
      store.setPlaybackError(err.message);
    }
  }, [store]);

  // Consolidated playback control — single effect manages src loading + play/pause
  // Fixes stutter caused by two separate effects racing: one setting src, one calling play()
  useEffect(() => {
    if (!audio) return;

    if (!store.isThisDeviceActive) {
      audio.pause();
      return;
    }

    if (!store.currentTrack) return;

    const trackChanged = store.currentTrack.id !== lastLoadedTrackIdRef.current;

    if (trackChanged) {
      // New track — set src and wait for canplay before playing
      lastLoadedTrackIdRef.current = store.currentTrack.id;
      const onCanPlay = (): void => {
        audio.removeEventListener('canplay', onCanPlay);
        if (store.isPlaying) {
          audio.play().catch(handlePlayError);
        }
      };
      audio.addEventListener('canplay', onCanPlay);
      audio.src = `/api/tracks/${store.currentTrack.id}/stream`;
      audio.currentTime = getCurrentPosition(store) / 1000;

      return () => audio.removeEventListener('canplay', onCanPlay);
    }

    // Same track — just toggle play/pause
    if (store.isPlaying && audio.paused) {
      audio.play().catch(handlePlayError);
    } else if (!store.isPlaying && !audio.paused) {
      audio.pause();
    }
  }, [audio, store.isThisDeviceActive, store.currentTrack?.id, store.isPlaying, handlePlayError]);

  // Sync audio position on explicit seek operations only (not on track start/state broadcasts)
  useEffect(() => {
    if (!audio || !store.isThisDeviceActive || !store.currentTrack) return;
    if (store.lastSeekAt === 0) return; // No seek has happened yet

    const expectedPosition = getCurrentPosition(store) / 1000;
    const actualPosition = audio.currentTime;

    if (Math.abs(expectedPosition - actualPosition) > 1) {
      audio.currentTime = expectedPosition;
    }
  }, [audio, store.lastSeekAt, store.isThisDeviceActive, store.currentTrack]);

  // Scrobble tracking - fire onTrackPlayed at 50% or 30s (once per playthrough)
  useEffect(() => {
    if (!store.isPlaying || !store.isThisDeviceActive || !store.currentTrack) return;
    if (store.scrobbledThisPlaythrough) return;

    const duration = (store.currentTrack.duration ?? 0) * 1000;
    const threshold = Math.min(duration * 0.5, 30000);

    const checkScrobble = () => {
      const position = getCurrentPosition(store);
      if (position >= threshold && !store.scrobbledThisPlaythrough) {
        store.onTrackPlayed(store.currentTrack!.id, position);
      }
    };

    const timeout = setTimeout(checkScrobble, threshold - store.positionMs);
    return () => clearTimeout(timeout);
  }, [store.currentTrack?.id, store.isPlaying, store.scrobbledThisPlaythrough]);

  // Gapless playback - preload next track 5s before end
  useEffect(() => {
    if (!audio) return;
    if (!store.isThisDeviceActive || !store.currentTrack) return;

    const onTimeUpdate = () => {
      if (audio.duration - audio.currentTime < 5) {
        store.preloadNextTrack();
      }
    };

    audio.addEventListener('timeupdate', onTimeUpdate);
    return () => audio.removeEventListener('timeupdate', onTimeUpdate);
  }, [audio, store.currentTrack?.id]);

  // Error handling - retry or skip on audio load failure
  useEffect(() => {
    if (!audio) return;

    const onError = () => {
      store.setPlaybackError(`Failed to load: ${store.currentTrack?.title}`);
      // Auto-skip to next track after 2s
      setTimeout(() => store.next(), 2000);
    };

    audio.addEventListener('error', onError);
    return () => audio.removeEventListener('error', onError);
  }, [audio, store.currentTrack?.id]);

  // Track ended - advance to next track (unless in comparison mode)
  useEffect(() => {
    if (!audio) return;
    if (!store.isThisDeviceActive) return;

    const onEnded = () => {
      // Comparison mode handles A/B switching via onFinish callback in ComparisonView
      // Don't auto-advance queue - let the component decide what to play next
      if (store.currentContext?.type === 'comparison') return;
      store.next();
    };

    audio.addEventListener('ended', onEnded);
    return () => audio.removeEventListener('ended', onEnded);
  }, [audio, store.currentTrack?.id, store.isThisDeviceActive, store.currentContext?.type]);

  return store;
}
