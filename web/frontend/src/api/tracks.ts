import type { WaveformData } from '../types';

export function getStreamUrl(trackId: number): string {
  return `/api/tracks/${trackId}/stream`;
}

export async function getWaveformData(trackId: number): Promise<WaveformData> {
  const response = await fetch(`/api/tracks/${trackId}/waveform`);
  if (!response.ok) {
    throw new Error(`Failed to fetch waveform: ${response.statusText}`);
  }
  return response.json();
}

export async function archiveTrack(trackId: number): Promise<void> {
  const response = await fetch(`/api/tracks/${trackId}/archive`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error(`Failed to archive track: ${response.statusText}`);
  }
}