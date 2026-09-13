import { useCallback, useEffect, useRef } from 'react';
import {
  recordError,
  clearErrorWindow,
  decidePlaybackError,
  shouldSuppressPrunedSkip,
  probeStreamForReauth,
  initialErrorWindow,
  PLAYBACK_BREAKER_MESSAGE,
  SOUNDCLOUD_REAUTH_MESSAGE,
  type ErrorWindowState,
  type Track,
} from '@music-minion/shared';
import { usePlayerStore, getCurrentPosition } from '../stores/playerStore';
import { useActiveAudioElement, useAudioPair, type AudioKey } from '../contexts/AudioElementContext';
import { bindTrackSource, clearTrackSource, streamUrlFor } from '../lib/audioSource';

const HAVE_CURRENT_DATA = 2;
const PRELOAD_DEBOUNCE_MS = 500;
// Signed SoundCloud CDN URLs (behind the proxy 302) expire in ~15min; treat a
// preloaded src older than this as stale and re-resolve instead of swapping.
const PRELOAD_MAX_AGE_MS = 10 * 60_000;

type PlayErrorHandler = (err: Error) => void;

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
  track: Track,
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
  bindTrackSource(inactive, track);
  inactive.dataset.trackId = String(track.id);
  inactive.dataset.srcBoundAt = String(Date.now());
  inactive.currentTime = 0;
}

/**
 * Re-resolve the SAME track on the active element after an audio error.
 * A fresh load of the proxy URL follows a fresh 302 to a new signed CDN URL,
 * recovering from expired URLs and transient network blips without skipping.
 * Restores playback position after canplay if the error hit mid-track.
 */
function retrySameTrack(
  el: HTMLAudioElement,
  track: Track,
  signal: AbortSignal,
  handlePlayError: PlayErrorHandler,
): void {
  const resumeAt = el.currentTime;
  el.pause();
  clearTrackSource(el);
  el.addEventListener(
    'canplay',
    () => {
      if (resumeAt > 0) el.currentTime = resumeAt;
      if (usePlayerStore.getState().isPlaying) {
        el.play().catch(handlePlayError);
      }
    },
    { once: true, signal },
  );
  bindTrackSource(el, track);
  el.dataset.trackId = String(track.id);
  el.dataset.srcBoundAt = String(Date.now());
  if (import.meta.env.DEV) {
    console.debug('[player] audio error — retrying same track with fresh stream URL', {
      trackId: track.id,
      resumeAt,
    });
  }
}

/**
 * Gapless local advance on `ended`: if the inactive element already holds the
 * next track, buffered and fresh, start it and flip the active key WITHOUT
 * waiting for the POST /next → broadcast round-trip. Returns false when the
 * preload isn't usable so the caller falls back to the server-driven path.
 */
function tryGaplessSwap(
  inactive: HTMLAudioElement,
  nextTrackId: number,
  setActiveKey: (k: AudioKey) => void,
  opposite: AudioKey,
  handlePlayError: PlayErrorHandler,
): boolean {
  const srcBoundAt = Number(inactive.dataset.srcBoundAt ?? '0');
  const preloadIsFresh = Date.now() - srcBoundAt < PRELOAD_MAX_AGE_MS;
  if (
    inactive.dataset.trackId !== String(nextTrackId)
    || inactive.readyState < HAVE_CURRENT_DATA
    || !preloadIsFresh
  ) {
    return false;
  }
  inactive.currentTime = 0;
  inactive.play().catch(handlePlayError);
  setActiveKey(opposite);
  if (import.meta.env.DEV) {
    console.debug('[player] gapless local advance', { to: opposite, trackId: nextTrackId });
  }
  return true;
}

function bindPreload(
  inactive: HTMLAudioElement,
  track: Track,
  signal: AbortSignal,
): void {
  inactive.pause();
  clearTrackSource(inactive);
  bindTrackSource(inactive, track);
  inactive.dataset.trackId = String(track.id);
  inactive.dataset.srcBoundAt = String(Date.now());
  inactive.preload = 'auto';

  // Clear dataset.trackId on preload error so the next swap routes through
  // load-on-swap rather than trying to swap to a half-loaded element.
  inactive.addEventListener(
    'error',
    () => {
      delete inactive.dataset.trackId;
      delete inactive.dataset.srcBoundAt;
      if (import.meta.env.DEV) {
        console.warn('[player] preload error', {
          trackId: track.id,
          code: inactive.error?.code,
        });
      }
    },
    { once: true, signal },
  );

  if (import.meta.env.DEV) {
    console.debug('[player] preload bound', { trackId: track.id });
  }
}

/** Single-instance only — must only be called in PlayerBar. Creates audio-loading side-effects tied to shared audio elements. */
export function usePlayer() {
  const store = usePlayerStore();
  const activeAudio = useActiveAudioElement();
  const { audioA, audioB, activeKeyRef, setActiveKey } = useAudioPair();
  const lastLoadedTrackIdRef = useRef<number | null>(null);
  const errorWindowRef = useRef<ErrorWindowState>(initialErrorWindow);
  // Track id already given its one in-place retry this playthrough; reset on
  // track change so every playthrough gets one re-resolve before skipping.
  const retriedTrackIdRef = useRef<number | null>(null);

  // Audio ownership: this device must be the active playback target AND this
  // tab must hold the cross-tab audio-leader lock (lib/audioLeader.ts). Tabs
  // sharing the device-id without the lock are remote controls — binding
  // audio in them plays everything twice and their ended/error handlers
  // double-fire /next against the leader's playback.
  const isAudioOwner = store.isThisDeviceActive && store.isAudioLeader;

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

  // Device transfer / not the leader tab: when this tab must not own audio,
  // pause and clear both elements
  useEffect(() => {
    if (isAudioOwner) return;
    if (audioA) {
      audioA.pause();
      clearTrackSource(audioA);
      delete audioA.dataset.trackId;
      delete audioA.dataset.srcBoundAt;
    }
    if (audioB) {
      audioB.pause();
      clearTrackSource(audioB);
      delete audioB.dataset.trackId;
      delete audioB.dataset.srcBoundAt;
    }
    lastLoadedTrackIdRef.current = null;
  }, [audioA, audioB, isAudioOwner]);

  // Track-change handler: silence old active, swap or load-on-swap to new track.
  // CRITICAL: activeKeyRef.current is read inside the effect; activeKey is NOT in deps.
  // Including activeKey would cause setActiveKey() inside the effect to re-fire it,
  // which would re-evaluate the precondition against a half-loaded element and
  // trigger swap-back loops.
  useEffect(() => {
    if (!isAudioOwner) return;
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
    retriedTrackIdRef.current = null;
    const track = store.currentTrack;
    const activeKey = activeKeyRef.current;
    const oldActive = activeKey === 'A' ? audioA : audioB;
    const inactive = activeKey === 'A' ? audioB : audioA;
    const opposite: AudioKey = activeKey === 'A' ? 'B' : 'A';
    const controller = new AbortController();

    // Step 1: silence old active IMMEDIATELY (silence guarantee).
    // Order matters: pause before unbinding src, all before binding new src.
    oldActive.pause();
    clearTrackSource(oldActive);

    const expectedTrackId = String(trackId);

    // Preload staleness: the browser captured the signed CDN URL (via the
    // proxy 302) when the preload src was bound; if that was too long ago the
    // buffered URL may have expired mid-buffer. Re-resolve instead of swapping.
    const srcBoundAt = Number(inactive.dataset.srcBoundAt ?? '0');
    const preloadIsFresh = Date.now() - srcBoundAt < PRELOAD_MAX_AGE_MS;

    if (
      inactive.dataset.trackId === expectedTrackId
      && inactive.readyState >= HAVE_CURRENT_DATA
      && preloadIsFresh
    ) {
      swapToReadyInactive(inactive, setActiveKey, opposite, handlePlayError);
    } else {
      if (inactive.dataset.trackId === expectedTrackId && !preloadIsFresh) {
        // Clear the stale binding so the src assignment in loadAndSwap
        // triggers a fresh load (fresh 302 → fresh CDN URL).
        inactive.pause();
        clearTrackSource(inactive);
        if (import.meta.env.DEV) {
          console.debug('[player] stale preload — re-resolving before swap', { trackId });
        }
      }
      loadAndSwap(
        inactive,
        track,
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
    isAudioOwner,
    handlePlayError,
  ]);

  // Sync audio position on explicit seek operations
  useEffect(() => {
    if (!activeAudio || !isAudioOwner || !store.currentTrack) return;
    if (store.lastSeekAt === 0) return;

    const expectedPosition = getCurrentPosition(store) / 1000;
    const actualPosition = activeAudio.currentTime;

    if (Math.abs(expectedPosition - actualPosition) > 1) {
      activeAudio.currentTime = expectedPosition;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeAudio, store.lastSeekAt, isAudioOwner, store.currentTrack]);

  // Preload next track on the inactive element. Debounced 500ms to avoid
  // thrashing the backend SoundCloud resolver on rapid skips.
  useEffect(() => {
    if (!isAudioOwner) return;
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
      bindPreload(inactive, nextTrack, controller.signal);
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
    isAudioOwner,
  ]);

  // Scrobble tracking: fire onTrackPlayed at 50% or 30s (once per playthrough)
  useEffect(() => {
    if (!store.isPlaying || !isAudioOwner || !store.currentTrack) return;
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
  }, [store.currentTrack?.id, store.isPlaying, store.scrobbledThisPlaythrough, isAudioOwner]);

  // Error handler on active element with circuit breaker.
  // 3 errors within 10s trips the breaker and stops auto-skip cascade.
  // Before applying the policy, a short reauth probe checks whether the
  // backend is 503ing SoundCloud streams (revoked refresh token) — that is a
  // persistent condition where retry/skip would 503-walk the whole SC queue.
  // Otherwise each track gets ONE in-place retry (fresh proxy load → fresh
  // signed CDN URL) — expired stream URLs and transient blips recover without
  // losing the track. Second failure falls through to the skip path.
  // Reads store via getState() so the effect doesn't re-fire on every state update
  // (which would clear the in-flight skip timer via cleanup before it can fire).
  useEffect(() => {
    if (!activeAudio) return;

    const controller = new AbortController();
    let skipTimer: number | null = null;

    const scheduleSkip = (erroredTrackId: number | null): void => {
      if (skipTimer !== null) return;
      skipTimer = window.setTimeout(() => {
        skipTimer = null;
        // Re-read state at FIRE time: if the server pruned this dead track
        // (playback:state broadcast with pruned_track_id) it already
        // advanced — firing next() too would double-advance past a good track.
        const s = usePlayerStore.getState();
        if (shouldSuppressPrunedSkip(erroredTrackId, s.lastPrunedTrackId, s.lastPrunedAt, Date.now())) {
          if (import.meta.env.DEV) {
            console.debug('[player] error-skip suppressed — server pruned track', { erroredTrackId });
          }
          return;
        }
        s.next();
      }, 500);
    };

    const applyErrorPolicy = (trackId: number | undefined): void => {
      errorWindowRef.current = recordError(errorWindowRef.current, Date.now());

      const s = usePlayerStore.getState();
      // Retry eligibility is guarded on dataset.trackId so a mid-swap error
      // can't rebind the wrong track onto the active element; a mismatch makes
      // the track non-retryable (null) and the policy falls through to skip.
      const retryableTrackId =
        trackId != null && activeAudio.dataset.trackId === String(trackId)
          ? trackId
          : null;
      const decision = decidePlaybackError(
        errorWindowRef.current,
        retryableTrackId,
        retriedTrackIdRef.current,
      );

      if (decision === 'breaker') {
        s.setPlaybackError(PLAYBACK_BREAKER_MESSAGE);
        if (import.meta.env.DEV) {
          console.warn('[player] circuit breaker tripped', {
            errorsInWindow: errorWindowRef.current.errorTimes.length,
          });
        }
        return;
      }

      // Retry the SAME track once before skipping. Needs the full track
      // object (source drives HLS vs progressive binding); a server prune may
      // have advanced currentTrack, so fall back to a queue lookup.
      if (decision === 'retry' && retryableTrackId != null) {
        const retryTrack =
          s.currentTrack?.id === retryableTrackId
            ? s.currentTrack
            : s.queue.find((t) => t.id === retryableTrackId);
        if (retryTrack) {
          retriedTrackIdRef.current = retryableTrackId;
          retrySameTrack(activeAudio, retryTrack, controller.signal, handlePlayError);
          return;
        }
      }

      s.setPlaybackError(`Failed to load: ${s.currentTrack?.title}`);
      scheduleSkip(trackId ?? null);
    };

    const onError = (): void => {
      const s = usePlayerStore.getState();
      // Non-owner tabs keep their elements unbound; a stray error here must
      // never retry/skip against the leader tab's playback.
      if (!s.isThisDeviceActive || !s.isAudioLeader) return;
      // Capture the errored track id NOW — a server prune may advance
      // currentTrack while the probe is in flight.
      const trackId = s.currentTrack?.id;
      // Reauth probe FIRST (~3s timeout): the media element hides HTTP
      // status, and a revoked SoundCloud session 503s every SC stream.
      // Reauth is persistent — it never counts toward the error window and
      // never auto-skips. Probe failure/non-503 falls back to normal policy.
      const probe = trackId != null
        ? probeStreamForReauth(streamUrlFor(trackId))
        : Promise.resolve(false);
      void probe.then((needsReauth) => {
        if (needsReauth) {
          usePlayerStore.getState().setPlaybackError(SOUNDCLOUD_REAUTH_MESSAGE);
          return;
        }
        applyErrorPolicy(trackId);
      });
    };

    const onCanPlay = (): void => {
      // Sliding window self-recovers on first successful playback
      errorWindowRef.current = clearErrorWindow();
    };

    activeAudio.addEventListener('error', onError);
    activeAudio.addEventListener('canplay', onCanPlay);
    return (): void => {
      controller.abort();
      if (skipTimer !== null) clearTimeout(skipTimer);
      activeAudio.removeEventListener('error', onError);
      activeAudio.removeEventListener('canplay', onCanPlay);
    };
  }, [activeAudio, handlePlayError]);

  // Track ended: advance to next track (unless in comparison mode, which handles
  // its own A/B switching via onFinish callback in ComparisonView).
  // Gapless fast-path: when the inactive element has the next track preloaded
  // and ready, swap locally FIRST (no audio gap), optimistically advance the
  // store, then POST /next to reconcile. The broadcast is either an echo
  // (same track/index — syncState suppresses or no-ops; the track-change
  // effect sees lastLoadedTrackIdRef already updated and does not reload) or a
  // divergence (server pruned a dead track), in which case syncState replaces
  // currentTrack and the track-change effect hard-corrects to server truth.
  useEffect(() => {
    if (!activeAudio) return;

    const onEnded = (): void => {
      const s = usePlayerStore.getState();
      if (!s.isThisDeviceActive || !s.isAudioLeader) return;
      if (s.currentContext?.type === 'comparison') return;
      // A local advance is already awaiting its reconcile broadcast —
      // suppress duplicate advance triggers until server truth arrives.
      if (s.pendingLocalAdvance) return;

      const nextTrack = s.queue[s.queueIndex + 1];
      if (nextTrack && s.isPlaying && audioA && audioB) {
        const activeKey = activeKeyRef.current;
        const inactive = activeKey === 'A' ? audioB : audioA;
        const opposite: AudioKey = activeKey === 'A' ? 'B' : 'A';
        if (tryGaplessSwap(inactive, nextTrack.id, setActiveKey, opposite, handlePlayError)) {
          // Mark the swap done BEFORE the store update so the track-change
          // effect takes its same-track branch instead of reloading.
          lastLoadedTrackIdRef.current = nextTrack.id;
          retriedTrackIdRef.current = null;
          // advanceLocal sets pendingLocalAdvance, which tells next() to skip
          // its own optimistic advance — no double-skip from this pair.
          s.advanceLocal();
          s.next();
          return;
        }
      }
      // Queue exhausted or preload not usable — server-driven advance.
      s.next();
    };

    activeAudio.addEventListener('ended', onEnded);
    return () => activeAudio.removeEventListener('ended', onEnded);
  }, [activeAudio, audioA, audioB, activeKeyRef, setActiveKey, handlePlayError]);

  return store;
}
