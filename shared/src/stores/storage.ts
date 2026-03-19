/**
 * Platform-agnostic storage adapter.
 * Web: wraps localStorage (sync)
 * RN:  wraps AsyncStorage (async, but we cache reads at init)
 */
export interface StorageAdapter {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
  removeItem: (key: string) => void;
}

/**
 * Web localStorage adapter (default).
 * Only usable in browser environments.
 */
export const createWebStorageAdapter = (): StorageAdapter => ({
  getItem: (key) => localStorage.getItem(key),
  setItem: (key, value) => localStorage.setItem(key, value),
  removeItem: (key) => localStorage.removeItem(key),
});

/**
 * In-memory adapter for testing / SSR.
 */
export const createMemoryStorageAdapter = (): StorageAdapter => {
  const store = new Map<string, string>();
  return {
    getItem: (key) => store.get(key) ?? null,
    setItem: (key, value) => store.set(key, value),
    removeItem: (key) => store.delete(key),
  };
};
