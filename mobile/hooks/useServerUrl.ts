/**
 * Manages the server URL in AsyncStorage.
 * First-run flow: isConfigured=false → setup screen → save URL → isConfigured=true.
 */
import { useState, useEffect, useCallback } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY = 'music-minion-server-url';

// Fall back to env var if set
const ENV_URL = process.env.EXPO_PUBLIC_API_URL;

interface ServerUrlState {
  serverUrl: string | null;
  isConfigured: boolean;
  isLoading: boolean;
  saveServerUrl: (url: string) => Promise<void>;
}

export const useServerUrl = (): ServerUrlState => {
  const [serverUrl, setServerUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY).then((stored) => {
      const url = stored ?? ENV_URL ?? null;
      setServerUrl(url);
      setIsLoading(false);
    });
  }, []);

  const saveServerUrl = useCallback(async (url: string) => {
    await AsyncStorage.setItem(STORAGE_KEY, url);
    setServerUrl(url);
  }, []);

  return {
    serverUrl,
    isConfigured: !isLoading && serverUrl !== null,
    isLoading,
    saveServerUrl,
  };
};
