import { useEffect } from 'react';
import { usePlayerStore, getCurrentPosition } from '../stores/playerStore';
import { useAudioElement } from '../contexts/AudioElementContext';

export function usePlayer() {
  const store = usePlayerStore();
  const audio = useAudioElement();

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

  // Control playback based on device state and track
  useEffect(() => {
    if (!audio) return;

    if (!store.isThisDeviceActive) {
      audio.pause();
      return;
    }

    if (store.currentTrack) {
      const newSrc = `/api/tracks/${store.currentTrack.id}/stream`;
      if (audio.src !== newSrc) {
        audio.src = newSrc;
        audio.currentTime = getCurrentPosition(store) / 1000;
      }
    }
  }, [audio, store.isThisDeviceActive, store.currentTrack?.id, store.isPlaying]);

  // Sync audio position on seek operations
  useEffect(() => {
    if (!audio || !store.isThisDeviceActive || !store.currentTrack) return;

    const expectedPosition = getCurrentPosition(store) / 1000;
    const actualPosition = audio.currentTime;

    // If difference > 1s, sync (likely a seek operation, not natural drift)
    if (Math.abs(expectedPosition - actualPosition) > 1) {
      audio.currentTime = expectedPosition;
    }
  }, [audio, store.positionMs, store.trackStartedAt, store.isThisDeviceActive, store.currentTrack]);

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

  // Mobile audio constraints - iOS Safari requires user gesture
  useEffect(() => {
    if (!audio) return;
    if (!store.isThisDeviceActive) return;
    if (!store.currentTrack || !store.isPlaying) return;

    audio.play().catch((err) => {
      if (err.name === 'NotAllowedError') {
        // iOS Safari blocked autoplay - need user gesture
        store.set({ needsUserGesture: true });
      } else {
        store.setPlaybackError(err.message);
      }
    });
  }, [audio, store.isThisDeviceActive, store.currentTrack, store.isPlaying]);

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

  // Track ended - advance to next track
  useEffect(() => {
    if (!audio) return;
    if (!store.isThisDeviceActive) return;

    const onEnded = () => {
      store.next();
    };

    audio.addEventListener('ended', onEnded);
    return () => audio.removeEventListener('ended', onEnded);
  }, [audio, store.currentTrack?.id, store.isThisDeviceActive]);

  return store;
}
