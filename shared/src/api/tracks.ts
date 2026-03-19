/**
 * Track API — portable layer (no DOM dependencies).
 * Web-specific features (waveform cache, link prefetch) stay in web/frontend.
 */
import { getDefaultApiClient } from './client.js';
import type { WaveformData, FoldersResponse } from '../types/index.js';

export function getStreamUrl(trackId: number): string {
  return `${getDefaultApiClient().getBaseUrl()}/tracks/${trackId}/stream`;
}

export async function getWaveformData(trackId: number): Promise<WaveformData> {
  return getDefaultApiClient().request<WaveformData>(`/tracks/${trackId}/waveform`);
}

export async function checkStreamAvailable(trackId: number): Promise<boolean> {
  try {
    const response = await fetch(`${getDefaultApiClient().getBaseUrl()}/tracks/${trackId}/stream`, { method: 'HEAD' });
    return response.ok;
  } catch {
    return false;
  }
}

export async function archiveTrack(trackId: number): Promise<void> {
  const baseUrl = getDefaultApiClient().getBaseUrl();
  const response = await fetch(`${baseUrl}/tracks/${trackId}/archive`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`Failed to archive track: ${response.statusText}`);
  }
}

export async function refreshWaveform(trackId: number): Promise<WaveformData> {
  const baseUrl = getDefaultApiClient().getBaseUrl();
  await fetch(`${baseUrl}/tracks/${trackId}/waveform`, { method: 'DELETE' });
  return getWaveformData(trackId);
}

export async function purgeSoundcloudWaveforms(): Promise<{ purged: number }> {
  const baseUrl = getDefaultApiClient().getBaseUrl();
  const response = await fetch(`${baseUrl}/waveforms/purge-soundcloud`, { method: 'POST' });
  if (!response.ok) throw new Error(`Purge failed: ${response.statusText}`);
  return response.json() as Promise<{ purged: number }>;
}

export async function getFolders(parent?: string): Promise<FoldersResponse> {
  const baseUrl = getDefaultApiClient().getBaseUrl();
  const url = parent ? `${baseUrl}/folders?parent=${encodeURIComponent(parent)}` : `${baseUrl}/folders`;
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch folders: ${response.statusText}`);
  }
  return response.json();
}
