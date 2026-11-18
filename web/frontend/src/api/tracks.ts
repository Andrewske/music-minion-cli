/**
 * Track API — web-specific wrapper with DOM-based caching.
 * Core functions re-exported from shared, web-only additions here.
 */
import { getWaveformData as sharedGetWaveformData } from '@music-minion/shared';
import type { WaveformData } from '@music-minion/shared';

// Re-export portable functions
export {
  checkStreamAvailable,
  purgeSoundcloudWaveforms,
  getFolders,
  getTrackNotes,
  saveTrackNotes,
} from '@music-minion/shared';

/** React Query key for a track's waveform peaks. */
export function waveformQueryKey(trackId: number | null): readonly ['waveform', number | null] {
  return ['waveform', trackId] as const;
}

// In-memory cache for prefetched waveforms (web-only)
const waveformCache = new Map<number, Promise<WaveformData>>();

export async function getWaveformData(trackId: number): Promise<WaveformData> {
  const cached = waveformCache.get(trackId);
  if (cached) return cached;

  const promise = sharedGetWaveformData(trackId);
  waveformCache.set(trackId, promise);
  return promise;
}

/**
 * Prefetch waveform peaks (web-only). Deliberately NOT the audio: a
 * <link rel="prefetch"> pulled both whole files at idle priority, and the
 * <audio> element's request for the same URL appeared to wait on that
 * download (10-15s to first sound on mobile). The element's own Range
 * request starts playback after a few hundred KB.
 */
export function prefetchWaveform(trackId: number): void {
  if (waveformCache.has(trackId)) return;
  getWaveformData(trackId).catch(() => {
    waveformCache.delete(trackId);
  });
}

export async function refreshWaveform(trackId: number): Promise<WaveformData> {
  // Delete backend cache
  const { refreshWaveform: sharedRefresh } = await import('@music-minion/shared');
  waveformCache.delete(trackId);
  return sharedRefresh(trackId);
}
