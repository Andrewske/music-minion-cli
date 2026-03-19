/**
 * Track API — web-specific wrapper with DOM-based caching.
 * Core functions re-exported from shared, web-only additions here.
 */
import {
  getStreamUrl as sharedGetStreamUrl,
  getWaveformData as sharedGetWaveformData,
} from '@music-minion/shared';
import type { WaveformData } from '@music-minion/shared';

// Re-export portable functions
export {
  checkStreamAvailable,
  archiveTrack,
  purgeSoundcloudWaveforms,
  getFolders,
} from '@music-minion/shared';

// In-memory cache for prefetched waveforms (web-only)
const waveformCache = new Map<number, Promise<WaveformData>>();

export function getStreamUrl(trackId: number): string {
  return sharedGetStreamUrl(trackId);
}

export async function getWaveformData(trackId: number): Promise<WaveformData> {
  const cached = waveformCache.get(trackId);
  if (cached) return cached;

  const promise = sharedGetWaveformData(trackId);
  waveformCache.set(trackId, promise);
  return promise;
}

/**
 * Prefetch waveform data + audio stream (web-only, uses DOM).
 */
export function prefetchWaveform(trackId: number): void {
  if (!waveformCache.has(trackId)) {
    getWaveformData(trackId).catch(() => {
      waveformCache.delete(trackId);
    });
  }

  const streamUrl = getStreamUrl(trackId);
  const existingLink = document.querySelector(`link[href="${streamUrl}"]`);
  if (!existingLink) {
    const link = document.createElement('link');
    link.rel = 'prefetch';
    link.href = streamUrl;
    link.as = 'fetch';
    document.head.appendChild(link);
  }
}

export async function refreshWaveform(trackId: number): Promise<WaveformData> {
  // Delete backend cache
  const { refreshWaveform: sharedRefresh } = await import('@music-minion/shared');
  waveformCache.delete(trackId);
  return sharedRefresh(trackId);
}
