/**
 * Manages the server URL in AsyncStorage.
 * First-run flow: isConfigured=false → setup screen → save URL → isConfigured=true.
 * Shared module-level state so all consumers update together.
 */
import { useState, useEffect, useCallback } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = 'music-minion-server-url';

/**
 * Returns the env URL only if it is a usable remote address.
 * Blank or localhost/127.0.0.1 values are unreachable from a physical
 * device, so they fall through to null → mandatory setup gate.
 */
const usableEnvUrl = (): string | null => {
  const raw = process.env.EXPO_PUBLIC_API_URL?.trim();
  if (!raw) return null;
  if (/(?:localhost|127\.0\.0\.1)/i.test(raw)) return null;
  return raw;
};

const ENV_URL = usableEnvUrl();

interface ServerUrlState {
  serverUrl: string | null;
  isConfigured: boolean;
  isLoading: boolean;
  saveServerUrl: (url: string) => Promise<void>;
}

interface SharedState {
  serverUrl: string | null;
  isLoading: boolean;
}

let shared: SharedState = { serverUrl: null, isLoading: true };
const listeners = new Set<(s: SharedState) => void>();
let hydratePromise: Promise<void> | null = null;

const setShared = (next: SharedState): void => {
  shared = next;
  listeners.forEach((fn) => fn(shared));
};

const hydrate = (): Promise<void> => {
  if (hydratePromise) return hydratePromise;
  hydratePromise = AsyncStorage.getItem(STORAGE_KEY).then((stored) => {
    const saved = stored?.trim() || null;
    setShared({ serverUrl: saved ?? ENV_URL ?? null, isLoading: false });
  });
  return hydratePromise;
};

export const useServerUrl = (): ServerUrlState => {
  const [state, setState] = useState<SharedState>(shared);

  useEffect(() => {
    let mounted = true;
    const listener = (s: SharedState): void => {
      if (mounted) setState(s);
    };
    listeners.add(listener);
    hydrate();
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const saveServerUrl = useCallback(async (url: string): Promise<void> => {
    await AsyncStorage.setItem(STORAGE_KEY, url);
    setShared({ serverUrl: url, isLoading: false });
  }, []);

  return {
    serverUrl: state.serverUrl,
    isConfigured: !state.isLoading && state.serverUrl !== null,
    isLoading: state.isLoading,
    saveServerUrl,
  };
};
