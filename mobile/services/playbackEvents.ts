/**
 * Single owner of RNTP playback event side-effects: advance-on-end and
 * error retry/skip/circuit-breaker.
 *
 * WHY ONE MODULE (dedupe decision): RNTP's Android layer delivers each event
 * to EXACTLY ONE JS path — the foreground NativeEventEmitter when the app
 * process is foregrounded, or the 'TrackPlayerServiceBridge' headless task
 * when backgrounded (see @rntp/player android ReactApplicationContextExt.kt:
 * emitEvent() branches on isAppOnForeground()). So neither path can be
 * dropped: the foreground listener never fires while backgrounded and vice
 * versa. Both entry points (usePlayer's listeners and the background handler
 * in services/playback.ts) therefore delegate HERE, so end/error logic exists
 * once. Module-level timestamp guards additionally collapse duplicates from
 * (a) the foreground/background transition edge and (b) multiple usePlayer
 * mounts (PlayerBar + NowPlaying) — historically each mount registered its
 * own listeners and double-advanced on Ended.
 */
import TrackPlayer, {
  Event,
  PlaybackState,
  type BackgroundEvent,
} from '@rntp/player';
import {
  getStreamUrl,
  getDefaultApiClient,
  recordError,
  clearErrorWindow,
  decidePlaybackError,
  shouldSuppressPrunedSkip,
  probeStreamForReauth,
  initialErrorWindow,
  PLAYBACK_BREAKER_MESSAGE,
  SOUNDCLOUD_REAUTH_MESSAGE,
  type ErrorWindowState,
  type PlayerStore,
} from '@music-minion/shared';
import { usePlayerStore } from '../stores/playerStore';

/** Same physical event surfacing twice (dual listeners, fg/bg edge) lands well inside this. */
const DEDUPE_WINDOW_MS = 1_000;
/** Delay before skipping a dead track — matches previous mobile behavior. */
const SKIP_DELAY_MS = 2_000;

// ── Module state (one JS runtime serves both foreground and headless paths) ──
let errorWindow: ErrorWindowState = initialErrorWindow;
let retriedTrackId: number | null = null;
let lastEndedHandledAt = 0;
let lastErrorHandledAt = 0;
let skipTimer: ReturnType<typeof setTimeout> | null = null;
let foregroundListenersRegistered = false;

/** Backend artwork URL — baseUrl already includes the `/api` prefix. */
function getArtworkUrl(trackId: number): string {
  return `${getDefaultApiClient().getBaseUrl()}/tracks/${trackId}/artwork`;
}

/**
 * New playthrough — give the incoming track its one in-place retry.
 * Called by usePlayer's load effect, which is already gated on track change.
 */
export function resetRetryTracking(): void {
  retriedTrackId = null;
}

/**
 * Retry the SAME track once by re-setting the media item. The cache-buster
 * forces a fresh request through the backend proxy → fresh signed SoundCloud
 * CDN URL (mirrors web's retrySameTrack re-resolve).
 */
function retryCurrentTrack(store: PlayerStore): void {
  const track = store.currentTrack;
  if (!track) return;
  try {
    TrackPlayer.setMediaItem({
      mediaId: String(track.id),
      url: `${getStreamUrl(track.id)}?retry=${Date.now()}`,
      title: track.title,
      artist: track.artist ?? 'Unknown Artist',
      duration: track.duration,
      artworkUrl: getArtworkUrl(track.id),
    });
    if (store.isPlaying) TrackPlayer.play();
  } catch {
    // Retry mechanics failed outright — surface and fall through to skip path
    store.setPlaybackError(`Failed to load: ${track.title}`);
    scheduleSkip(track.id);
  }
}

function scheduleSkip(erroredTrackId: number | null): void {
  if (skipTimer !== null) return;
  skipTimer = setTimeout(() => {
    skipTimer = null;
    // Re-read state at FIRE time: if the server pruned this dead track
    // (playback:state broadcast with pruned_track_id) it already advanced —
    // firing next() too would double-advance past a good track.
    const store = usePlayerStore.getState();
    if (shouldSuppressPrunedSkip(erroredTrackId, store.lastPrunedTrackId, store.lastPrunedAt, Date.now())) {
      return;
    }
    store.next();
  }, SKIP_DELAY_MS);
}

function handleEnded(now: number): void {
  if (now - lastEndedHandledAt < DEDUPE_WINDOW_MS) return;
  lastEndedHandledAt = now;

  const store = usePlayerStore.getState();
  // Comparison mode drives its own A/B switching
  if (store.currentContext?.type !== 'comparison') {
    store.next();
  }
}

function handleError(now: number): void {
  if (now - lastErrorHandledAt < DEDUPE_WINDOW_MS) return;
  lastErrorHandledAt = now;

  // Capture the errored track id NOW — a server prune may advance
  // currentTrack while the reauth probe is in flight.
  const trackId = usePlayerStore.getState().currentTrack?.id ?? null;
  void resolvePlaybackError(trackId, now);
}

/**
 * Reauth probe FIRST (~3s timeout): RNTP hides HTTP status, and a revoked
 * SoundCloud session 503s every SC stream — retry/skip would 503-walk the
 * whole queue. Reauth is persistent: it never counts toward the error window
 * and never auto-skips. Probe failure/non-503 falls back to normal policy.
 */
async function resolvePlaybackError(trackId: number | null, now: number): Promise<void> {
  if (trackId != null && (await probeStreamForReauth(getStreamUrl(trackId)))) {
    usePlayerStore.getState().setPlaybackError(SOUNDCLOUD_REAUTH_MESSAGE);
    return;
  }
  applyErrorPolicy(trackId, now);
}

function applyErrorPolicy(trackId: number | null, now: number): void {
  errorWindow = recordError(errorWindow, now);
  const store = usePlayerStore.getState();
  const decision = decidePlaybackError(errorWindow, trackId, retriedTrackId);

  if (decision === 'breaker') {
    // Persistent error; NO further skips — stops the runaway walk through a
    // dead/offline queue. User recovers via the banner's Retry (retryPlayback)
    // or organically: a successful load clears the window below.
    store.setPlaybackError(PLAYBACK_BREAKER_MESSAGE);
    return;
  }

  if (decision === 'retry' && trackId != null) {
    retriedTrackId = trackId;
    retryCurrentTrack(store);
    return;
  }

  store.setPlaybackError(`Failed to load: ${store.currentTrack?.title ?? 'Unknown'}`);
  scheduleSkip(trackId);
}

/**
 * Process one RNTP event. Safe to call from BOTH the foreground listeners and
 * the background headless handler — timestamp guards make it idempotent per
 * physical event.
 */
export function handlePlaybackEvent(event: BackgroundEvent): void {
  switch (event.type) {
    case Event.PlaybackStateChanged: {
      if (event.state === PlaybackState.Ready) {
        // Successful load — sliding error window self-recovers (web: canplay)
        errorWindow = clearErrorWindow();
      } else if (event.state === PlaybackState.Ended) {
        handleEnded(Date.now());
      }
      break;
    }
    case Event.PlaybackError: {
      handleError(Date.now());
      break;
    }
    default:
      break;
  }
}

/**
 * Register app-lifetime foreground listeners exactly once, no matter how many
 * usePlayer instances mount (PlayerBar + NowPlaying both mount it). Never
 * unregistered — playback events must be handled for the app's whole life.
 */
export function registerForegroundPlaybackListeners(): void {
  if (foregroundListenersRegistered) return;
  foregroundListenersRegistered = true;

  TrackPlayer.addEventListener(Event.PlaybackStateChanged, (event) => {
    handlePlaybackEvent({ type: Event.PlaybackStateChanged, state: event.state });
  });
  TrackPlayer.addEventListener(Event.PlaybackError, (event) => {
    handlePlaybackEvent({
      type: Event.PlaybackError,
      code: event.code,
      message: event.message,
    });
  });
}
