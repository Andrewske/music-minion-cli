import { useEffect, useRef } from 'react';
import { usePlayerStore, getCurrentPosition } from '../stores/playerStore';

export function usePlayer() {
  const store = usePlayerStore();
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Initialize device on mount
  useEffect(() => {
    store.registerDevice();
  }, [store]);

  // Audio element - persist across device switches, never destroy
  useEffect(() => {
    // Create audio element once on mount
    if (!audioRef.current) {
      audioRef.current = new Audio();
      audioRef.current.volume = store.volume;
      audioRef.current.muted = store.isMuted;
    }

    // Cleanup on unmount only
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = '';
        audioRef.current = null;
      }
    };
  }, []);

  // Update volume when store changes
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = store.volume;
    }
  }, [store.volume]);

  // Update mute when store changes
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.muted = store.isMuted;
    }
  }, [store.isMuted]);

  // Control playback based on device state and track
  useEffect(() => {
    const audio = audioRef.current;
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
  }, [store.isThisDeviceActive, store.currentTrack?.id, store.isPlaying]);

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
    if (!store.isThisDeviceActive || !store.currentTrack) return;

    const audio = audioRef.current;
    if (!audio) return;

    const onTimeUpdate = () => {
      if (audio.duration - audio.currentTime < 5) {
        store.preloadNextTrack();
      }
    };

    audio.addEventListener('timeupdate', onTimeUpdate);
    return () => audio.removeEventListener('timeupdate', onTimeUpdate);
  }, [store.currentTrack?.id]);

  // Mobile audio constraints - iOS Safari requires user gesture
  useEffect(() => {
    if (!store.isThisDeviceActive) return;
    if (!store.currentTrack || !store.isPlaying) return;

    const audio = audioRef.current;
    if (!audio) return;

    audio.play().catch((err) => {
      if (err.name === 'NotAllowedError') {
        // iOS Safari blocked autoplay - need user gesture
        store.set({ needsUserGesture: true });
      } else {
        store.setPlaybackError(err.message);
      }
    });
  }, [store.isThisDeviceActive, store.currentTrack, store.isPlaying]);

  // Error handling - retry or skip on audio load failure
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onError = () => {
      store.setPlaybackError(`Failed to load: ${store.currentTrack?.title}`);
      // Auto-skip to next track after 2s
      setTimeout(() => store.next(), 2000);
    };

    audio.addEventListener('error', onError);
    return () => audio.removeEventListener('error', onError);
  }, [store.currentTrack?.id]);

  return store;
}
