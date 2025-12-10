import type { WaveformData, FoldersResponse } from '../types';

// In-memory cache for prefetched waveforms
const waveformCache = new Map<number, Promise<WaveformData>>();

export function getStreamUrl(trackId: number): string {
  return `/api/tracks/${trackId}/stream`;
}

export async function getWaveformData(trackId: number): Promise<WaveformData> {
  // Check cache first
  const cached = waveformCache.get(trackId);
  if (cached) {
    return cached;
  }

  const promise = fetch(`/api/tracks/${trackId}/waveform`)
    .then(response => {
      if (!response.ok) {
        throw new Error(`Failed to fetch waveform: ${response.statusText}`);
      }
      return response.json();
    });

  waveformCache.set(trackId, promise);
  return promise;
}

/**
 * Prefetch waveform data in the background (fire and forget).
 * Also prefetches the audio stream to warm up browser cache.
 */
export function prefetchWaveform(trackId: number): void {
  // Prefetch waveform data
  if (!waveformCache.has(trackId)) {
    getWaveformData(trackId).catch(() => {
      // Silent fail - waveform will be loaded on demand
      waveformCache.delete(trackId);
    });
  }

  // Prefetch audio stream using link preload
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

export async function checkStreamAvailable(trackId: number): Promise<boolean> {
  try {
    const response = await fetch(`/api/tracks/${trackId}/stream`, { method: 'HEAD' });
    return response.ok;
  } catch {
    return false;
  }
}

export async function archiveTrack(trackId: number): Promise<void> {
  const response = await fetch(`/api/tracks/${trackId}/archive`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`Failed to archive track: ${response.statusText}`);
  }
}

export async function getFolders(): Promise<FoldersResponse> {
  const response = await fetch('/api/folders');
  if (!response.ok) {
    throw new Error(`Failed to fetch folders: ${response.statusText}`);
  }
  return response.json();
}