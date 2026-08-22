import Hls from 'hls.js';
import type { Track } from '@music-minion/shared';

// One Hls instance per audio element (the player owns two for gapless swaps).
const hlsByElement = new WeakMap<HTMLAudioElement, Hls>();

export function streamUrlFor(trackId: number): string {
  return `/api/tracks/${trackId}/stream`;
}

// SoundCloud dropped progressive MP3 streams (2026-08) — /stream now 307s to
// an HLS playlist for SC tracks, which only Safari can play natively.
function needsHls(track: Track): boolean {
  return track.source === 'soundcloud' && !track.local_path;
}

function destroyHls(el: HTMLAudioElement): void {
  const hls = hlsByElement.get(el);
  if (!hls) return;
  hlsByElement.delete(el);
  hls.destroy();
}

function attachHls(el: HTMLAudioElement, url: string): void {
  const hls = new Hls();
  hlsByElement.set(el, hls);
  hls.on(Hls.Events.ERROR, (_event, data): void => {
    if (!data.fatal) return;
    destroyHls(el);
    if (data.details === Hls.ErrorDetails.MANIFEST_PARSING_ERROR) {
      // Redirect target wasn't an HLS playlist after all (progressive MP3 or
      // 30s preview) — rebind as a plain src instead of surfacing an error.
      el.src = url;
      return;
    }
    // Surface HLS-level failures (410 dead track, 503 reauth, segment loss)
    // as an element error so usePlayer's retry/skip/reauth policy runs.
    el.dispatchEvent(new Event('error'));
  });
  hls.loadSource(url);
  hls.attachMedia(el);
}

/**
 * Bind a track's stream to an audio element. Remote SoundCloud tracks are
 * HLS-only and go through hls.js (MSE); everything else is a plain
 * progressive src. Browsers without MSE (iOS Safari) fall through to the
 * plain src path, which plays the HLS playlist natively.
 */
export function bindTrackSource(el: HTMLAudioElement, track: Track): void {
  destroyHls(el);
  if (needsHls(track) && Hls.isSupported()) {
    attachHls(el, streamUrlFor(track.id));
    return;
  }
  el.src = streamUrlFor(track.id);
}

/** Unbind any source (progressive or HLS/MSE) and reset the element. */
export function clearTrackSource(el: HTMLAudioElement): void {
  destroyHls(el);
  el.removeAttribute('src');
  el.load();
}
