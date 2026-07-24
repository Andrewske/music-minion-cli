/**
 * Mobile player store — injects RN-specific deps into shared factory.
 */
import { createPlayerStore, getCurrentPosition, getDefaultApiClient } from '@music-minion/shared';
import type { PlayContext, PlayerStore } from '@music-minion/shared';
import type { StorageAdapter } from '@music-minion/shared';
import AsyncStorage from '@react-native-async-storage/async-storage';

const getApiBase = (): string => {
  try {
    return getDefaultApiClient().getBaseUrl();
  } catch {
    return process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8642/api';
  }
};

/**
 * AsyncStorage adapter — the store is created synchronously at module import,
 * so reads go through an in-memory cache. The cache starts empty; call
 * `hydrateStorage()` at app startup (before any WebSocket device:register)
 * to load persisted values and reconcile them into the live store.
 */
const cache = new Map<string, string>();
const DEVICE_ID_KEY = 'music-minion-device-id';
const KEYS_TO_HYDRATE = [
  DEVICE_ID_KEY,
  'music-minion-device-name',
  'music-minion-volume',
  'music-minion-player-muted',
  'music-minion-shuffle',
];

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

/**
 * Provisional device ID at import time — cached in memory only, NOT persisted.
 * Persisting here would overwrite the real stored ID before hydration runs.
 * `hydrateStorage()` either replaces it with the persisted ID or (on first
 * launch) persists it.
 */
function generateDeviceId(): string {
  const cached = cache.get(DEVICE_ID_KEY);
  if (cached) return cached;

  // crypto.randomUUID() available in RN Hermes
  const uuid = crypto.randomUUID();
  cache.set(DEVICE_ID_KEY, uuid);
  return uuid;
}

function getDeviceName(): string {
  const custom = asyncStorageAdapter.getItem('music-minion-device-name');
  if (custom) return custom;
  return 'Android Phone';
}

export const usePlayerStore = createPlayerStore({
  storage: asyncStorageAdapter,
  apiBase: getApiBase,
  getDeviceName,
  generateDeviceId,
});

/** Push hydrated persisted values into the already-created store. */
const applyHydratedState = (persistedDeviceId: string | null): void => {
  const state = usePlayerStore.getState();

  if (persistedDeviceId === null) {
    // First launch: persist the provisional ID so it survives restarts
    asyncStorageAdapter.setItem(DEVICE_ID_KEY, state.thisDeviceId);
  }

  usePlayerStore.setState({
    thisDeviceId: persistedDeviceId ?? state.thisDeviceId,
    thisDeviceName: getDeviceName(),
    volume: parseFloat(cache.get('music-minion-volume') ?? '1.0'),
    isMuted: cache.get('music-minion-player-muted') === 'true',
    shuffleEnabled: cache.get('music-minion-shuffle') !== 'false',
  });
};

const doHydrate = async (): Promise<void> => {
  const pairs = await AsyncStorage.multiGet(KEYS_TO_HYDRATE);
  let persistedDeviceId: string | null = null;
  for (const [key, value] of pairs) {
    if (value === null) continue;
    cache.set(key, value);
    if (key === DEVICE_ID_KEY) persistedDeviceId = value;
  }
  applyHydratedState(persistedDeviceId);
};

let hydrationPromise: Promise<void> | null = null;

/**
 * Load persisted values from AsyncStorage into the cache and store.
 * Memoized — safe to call from multiple entry points. Await before
 * rendering anything that reads thisDeviceId (e.g. WebSocket sync).
 */
export const hydrateStorage = (): Promise<void> => {
  hydrationPromise ??= doHydrate();
  return hydrationPromise;
};

export { getCurrentPosition };
export type { PlayContext, PlayerStore };
