import { useCallback, useEffect, useRef } from 'react';
import { usePlayerStore, getCurrentPosition } from '../stores/playerStore';
import { useActiveAudioElement, useAudioPair, type AudioKey } from '../contexts/AudioElementContext';

const HAVE_CURRENT_DATA = 2;
const PRELOAD_DEBOUNCE_MS = 500;
const ERROR_WINDOW_MS = 10_000;
const ERROR_THRESHOLD = 3;

type PlayErrorHandler = (err: Error) => void;

function streamUrlFor(trackId: number): string {
  return `/api/tracks/${trackId}/stream`;
}

function swapToReadyInactive(
  inactive: HTMLAudioElement,
  setActiveKey: (k: AudioKey) => void,
  opposite: AudioKey,
  handlePlayError: PlayErrorHandler,
): void {
  setActiveKey(opposite);
  inactive.currentTime = 0;
  if (usePlayerStore.getState().isPlaying) {
    inactive.play().catch(handlePlayError);
  }
  if (import.meta.env.DEV) {
    console.debug('[player] swap', { to: opposite, fastPath: true });
  }
}

function loadAndSwap(
  inactive: HTMLAudioElement,
  url: string,
  expectedTrackId: string,
  signal: AbortSignal,
  setActiveKey: (k: AudioKey) => void,
  opposite: AudioKey,
  handlePlayError: PlayErrorHandler,
): void {
  inactive.addEventListener(
    'canplay',
    () => {
      setActiveKey(opposite);
      // Read isPlaying at fire time, not effect-run time. canplay can fire
      // 200-400ms after binding; user may have hit pause in that window.
      if (usePlayerStore.getState().isPlaying) {
        inactive.play().catch(handlePlayError);
      }
      if (import.meta.env.DEV) {
        console.debug('[player] swap', { to: opposite, fastPath: false });
      }
    },
    { once: true, signal },
  );
  inactive.src = url;
  inactive.dataset.trackId = expectedTrackId;
  inactive.currentTime = 0;
}

function bindPreload(
  inactive: HTMLAudioElement,
  trackId: number,
  signal: AbortSignal,
): void {
  inactive.pause();
  inactive.removeAttribute('src');
  inactive.load();
  inactive.src = streamUrlFor(trackId);
  inactive.dataset.trackId = String(trackId);
  inactive.preload = 'auto';

  // Clear dataset.trackId on preload error so the next swap routes through
  // load-on-swap rather than trying to swap to a half-loaded element.
  inactive.addEventListener(
    'error',
    () => {
      delete inactive.dataset.trackId;
      if (import.meta.env.DEV) {
        console.warn('[player] preload error', {
          trackId,
          code: inactive.error?.code,
        });
      }
    },
    { once: true, signal },
  );

  if (import.meta.env.DEV) {
    console.debug('[player] preload bound', { trackId });
  }
}

/** Single-instance only — must only be called in PlayerBar. Creates audio-loading side-effects tied to shared audio elements. */
export function usePlayer() {
  const store = usePlayerStore();
  const activeAudio = useActiveAudioElement();
  const { audioA, audioB, activeKeyRef, setActiveKey } = useAudioPair();
  const lastLoadedTrackIdRef = useRef<number | null>(null);
  const errorTimesRef = useRef<number[]>([]);

  // Initialize device on mount
  useEffect(() => {
    store.registerDevice();
  }, [store]);

  // Stable identity — reads/writes store via getState/setState so this callback
  // doesn't churn on every render. A fresh callback each render would put it in
  // effect dep arrays and re-run them, aborting in-flight canplay listeners
  // before the browser fires them.
  const handlePlayError = useCallback((err: Error): void => {
    if (err.name === 'NotAllowedError') {
      usePlayerStore.setState({ needsUserGesture: true });
    } else if (err.name !== 'AbortError') {
      usePlayerStore.getState().setPlaybackError(err.message);
    }
  }, []);

  // Volume/mute apply to BOTH elements every time
  useEffect(() => {
    if (audioA) audioA.volume = store.volume;
    if (audioB) audioB.volume = store.volume;
  }, [audioA, audioB, store.volume]);

  useEffect(() => {
    if (audioA) audioA.muted = store.isMuted;
    if (audioB) audioB.muted = store.isMuted;
  }, [audioA, audioB, store.isMuted]);

  // Device transfer: when local device becomes inactive, pause and clear both elements
  useEffect(() => {
    if (store.isThisDeviceActive) return;
    if (audioA) {
      audioA.pause();
      audioA.removeAttribute('src');
      audioA.load();
      delete audioA.dataset.trackId;
    }
    if (audioB) {
      audioB.pause();
      audioB.removeAttribute('src');
      audioB.load();
      delete audioB.dataset.trackId;
    }
    lastLoadedTrackIdRef.current = null;
  }, [audioA, audioB, store.isThisDeviceActive]);

  // Track-change handler: silence old active, swap or load-on-swap to new track.
  // CRITICAL: activeKeyRef.current is read inside the effect; activeKey is NOT in deps.
  // Including activeKey would cause setActiveKey() inside the effect to re-fire it,
  // which would re-evaluate the precondition against a half-loaded element and
  // trigger swap-back loops.
  useEffect(() => {
    if (!store.isThisDeviceActive) return;
    if (!store.currentTrack) return;
    if (!audioA || !audioB) return;

    const trackId = store.currentTrack.id;
    if (trackId === lastLoadedTrackIdRef.current) {
      // Same track — toggle play/pause on the active element
      const active = activeKeyRef.current === 'A' ? audioA : audioB;
      if (store.isPlaying && active.paused) {
        active.play().catch(handlePlayError);
      } else if (!store.isPlaying && !active.paused) {
        active.pause();
      }
      return;
    }

    lastLoadedTrackIdRef.current = trackId;
    const activeKey = activeKeyRef.current;
    const oldActive = activeKey === 'A' ? audioA : audioB;
    const inactive = activeKey === 'A' ? audioB : audioA;
    const opposite: AudioKey = activeKey === 'A' ? 'B' : 'A';
    const controller = new AbortController();

    // Step 1: silence old active IMMEDIATELY (silence guarantee).
    // Order matters: pause before removeAttribute before load, all before binding new src.
    oldActive.pause();
    oldActive.removeAttribute('src');
    oldActive.load();

    const expectedTrackId = String(trackId);
    const url = streamUrlFor(trackId);

    if (
      inactive.dataset.trackId === expectedTrackId
      && inactive.readyState >= HAVE_CURRENT_DATA
    ) {
      swapToReadyInactive(inactive, setActiveKey, opposite, handlePlayError);
    } else {
      loadAndSwap(
        inactive,
        url,
        expectedTrackId,
        controller.signal,
        setActiveKey,
        opposite,
        handlePlayError,
      );
    }

    return () => {
      controller.abort();
    };
  }, [
    audioA,
    audioB,
    activeKeyRef,
    setActiveKey,
    store.currentTrack,
    store.isPlaying,
    store.isThisDeviceActive,
    handlePlayError,
  ]);

  // Sync audio position on explicit seek operations
  useEffect(() => {
    if (!activeAudio || !store.isThisDeviceActive || !store.currentTrack) return;
    if (store.lastSeekAt === 0) return;

    const expectedPosition = getCurrentPosition(store) / 1000;
    const actualPosition = activeAudio.currentTime;

    if (Math.abs(expectedPosition - actualPosition) > 1) {
      activeAudio.currentTime = expectedPosition;
    }
  }, [activeAudio, store.lastSeekAt, store.isThisDeviceActive, store.currentTrack, store]);

  // Preload next track on the inactive element. Debounced 500ms to avoid
  // thrashing the backend SoundCloud resolver on rapid skips.
  useEffect(() => {
    if (!store.isThisDeviceActive) return;
    if (!store.currentTrack) return;
    if (store.currentContext?.type === 'comparison') return;
    if (!audioA || !audioB) return;

    const nextTrack = store.queue[store.queueIndex + 1];
    if (!nextTrack) return;

    const controller = new AbortController();
    const timeout = window.setTimeout(() => {
      const inactive = activeKeyRef.current === 'A' ? audioB : audioA;
      if (inactive.dataset.trackId === String(nextTrack.id)) return;
      // Swap-pending guard: if inactive holds the current track, it's the
      // load-on-swap target waiting for canplay. Overwriting its src here
      // would race the swap and play the preloaded track instead.
      if (
        store.currentTrack
        && inactive.dataset.trackId === String(store.currentTrack.id)
      ) return;
      bindPreload(inactive, nextTrack.id, controller.signal);
    }, PRELOAD_DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [
    audioA,
    audioB,
    activeKeyRef,
    store.currentTrack,
    store.queue,
    store.queueIndex,
    store.currentContext?.type,
    store.isThisDeviceActive,
  ]);

  // Scrobble tracking: fire onTrackPlayed at 50% or 30s (once per playthrough)
  useEffect(() => {
    if (!store.isPlaying || !store.isThisDeviceActive || !store.currentTrack) return;
    if (store.scrobbledThisPlaythrough) return;

    const duration = (store.currentTrack.duration ?? 0) * 1000;
    const threshold = Math.min(duration * 0.5, 30000);

    const checkScrobble = (): void => {
      const position = getCurrentPosition(store);
      if (position >= threshold && !store.scrobbledThisPlaythrough && store.currentTrack) {
        store.onTrackPlayed(store.currentTrack.id, position);
      }
    };

    const timeout = setTimeout(checkScrobble, threshold - store.positionMs);
    return () => clearTimeout(timeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [store.currentTrack?.id, store.isPlaying, store.scrobbledThisPlaythrough]);

  // Error handler on active element with circuit breaker.
  // 3 errors within 10s trips the breaker and stops auto-skip cascade.
  // Reads store via getState() so the effect doesn't re-fire on every state update
  // (which would clear the in-flight skip timer via cleanup before it can fire).
  useEffect(() => {
    if (!activeAudio) return;

    let skipTimer: number | null = null;
    const onError = (): void => {
      const now = Date.now();
      errorTimesRef.current = errorTimesRef.current
        .filter((t) => now - t < ERROR_WINDOW_MS)
        .concat(now);

      const s = usePlayerStore.getState();
      if (errorTimesRef.current.length >= ERROR_THRESHOLD) {
        s.setPlaybackError('Playback unavailable — check connection');
        if (import.meta.env.DEV) {
          console.warn('[player] circuit breaker tripped', {
            errorsInWindow: errorTimesRef.current.length,
          });
        }
        return;
      }

      s.setPlaybackError(`Failed to load: ${s.currentTrack?.title}`);
      if (skipTimer !== null) return;
      skipTimer = window.setTimeout(() => {
        skipTimer = null;
        usePlayerStore.getState().next();
      }, 500);
    };

    const onCanPlay = (): void => {
      // Sliding window self-recovers on first successful playback
      errorTimesRef.current = [];
    };

    activeAudio.addEventListener('error', onError);
    activeAudio.addEventListener('canplay', onCanPlay);
    return (): void => {
      if (skipTimer !== null) clearTimeout(skipTimer);
      activeAudio.removeEventListener('error', onError);
      activeAudio.removeEventListener('canplay', onCanPlay);
    };
  }, [activeAudio]);

  // Track ended: advance to next track (unless in comparison mode, which handles
  // its own A/B switching via onFinish callback in ComparisonView)
  useEffect(() => {
    if (!activeAudio) return;

    const onEnded = (): void => {
      const s = usePlayerStore.getState();
      if (!s.isThisDeviceActive) return;
      if (s.currentContext?.type === 'comparison') return;
      s.next();
    };

    activeAudio.addEventListener('ended', onEnded);
    return () => activeAudio.removeEventListener('ended', onEnded);
  }, [activeAudio]);

  return store;
}
