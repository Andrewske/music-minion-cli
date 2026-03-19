/**
 * Web player store — creates shared store with web-specific deps.
 */
import { createPlayerStore, getCurrentPosition, createWebStorageAdapter } from '@music-minion/shared';
import type { PlayContext, PlayerStore } from '@music-minion/shared';

const API_BASE = import.meta.env.VITE_API_BASE || '/api';

const storage = createWebStorageAdapter();

function generateDeviceId(): string {
  const stored = storage.getItem('music-minion-device-id');
  if (stored) return stored;

  const uuid = crypto.randomUUID();
  storage.setItem('music-minion-device-id', uuid);
  return uuid;
}

function getDeviceName(): string {
  const custom = storage.getItem('music-minion-device-name');
  if (custom) return custom;

  const ua = navigator.userAgent;
  let platform = 'Unknown';
  let browser = 'Unknown';

  if (/iPhone|iPad|iPod/.test(ua)) platform = 'iPhone';
  else if (/Android/.test(ua)) platform = 'Android';
  else if (/Macintosh/.test(ua)) platform = 'macOS';
  else if (/Windows/.test(ua)) platform = 'Windows';
  else if (/Linux/.test(ua)) platform = 'Linux';

  if (/Chrome/.test(ua) && !/Edg/.test(ua)) browser = 'Chrome';
  else if (/Safari/.test(ua) && !/Chrome/.test(ua)) browser = 'Safari';
  else if (/Firefox/.test(ua)) browser = 'Firefox';
  else if (/Edg/.test(ua)) browser = 'Edge';

  return `${platform} ${browser}`;
}

export const usePlayerStore = createPlayerStore({
  storage,
  apiBase: API_BASE,
  getDeviceName,
  generateDeviceId,
  preloadAudio: (url: string) => {
    const audio = new Audio();
    audio.src = url;
    audio.preload = 'auto';
  },
});

export { getCurrentPosition };
export type { PlayContext, PlayerStore };
