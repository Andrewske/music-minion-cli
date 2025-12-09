import type { WaveformData } from '../types';

export function getStreamUrl(trackId: number): string {
  const url = `/api/tracks/${trackId}/stream`;
  console.log('Stream URL:', url);
  return url;
}

export async function getWaveformData(trackId: number): Promise<WaveformData> {
  console.log('Fetching waveform for track:', trackId);
  const response = await fetch(`/api/tracks/${trackId}/waveform`);
  if (!response.ok) {
    throw new Error(`Failed to fetch waveform: ${response.statusText}`);
  }
  return response.json();
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