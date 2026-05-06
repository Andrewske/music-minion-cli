/**
 * Mobile player store — injects RN-specific deps into shared factory.
 */
import { createPlayerStore, getCurrentPosition } from '@music-minion/shared';
import type { PlayContext, PlayerStore } from '@music-minion/shared';
import type { StorageAdapter } from '@music-minion/shared';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE = process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8642/api';

/**
 * AsyncStorage adapter — caches reads synchronously after initial hydration.
 * Call `hydrate()` before creating the store.
 */
const cache = new Map<string, string>();
const KEYS_TO_HYDRATE = [
  'music-minion-device-id',
  'music-minion-device-name',
  'music-minion-volume',
  'music-minion-player-muted',
  'music-minion-shuffle',
];

export const hydrateStorage = async (): Promise<void> => {
  const pairs = await AsyncStorage.multiGet(KEYS_TO_HYDRATE);
  for (const [key, value] of pairs) {
    if (value !== null) cache.set(key, value);
  }
};

const asyncStorageAdapter: StorageAdapter = {
  getItem: (key) => cache.get(key) ?? null,
  setItem: (key, value) => {
    cache.set(key, value);
    AsyncStorage.setItem(key, value); // fire-and-forget
  },
  removeItem: (key) => {
    cache.delete(key);
    AsyncStorage.removeItem(key); // fire-and-forget
  },
};

function generateDeviceId(): string {
  const stored = asyncStorageAdapter.getItem('music-minion-device-id');
  if (stored) return stored;

  // crypto.randomUUID() available in RN Hermes
  const uuid = crypto.randomUUID();
  asyncStorageAdapter.setItem('music-minion-device-id', uuid);
  return uuid;
}

function getDeviceName(): string {
  const custom = asyncStorageAdapter.getItem('music-minion-device-name');
  if (custom) return custom;
  return 'Android Phone';
}

export const usePlayerStore = createPlayerStore({
  storage: asyncStorageAdapter,
  apiBase: API_BASE,
  getDeviceName,
  generateDeviceId,
});

export { getCurrentPosition };
export type { PlayContext, PlayerStore };
