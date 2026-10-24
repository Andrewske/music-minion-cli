/**
 * Root layout — providers, API client init, WebSocket sync, PlayerBar.
 */
import { useEffect, useMemo, useState } from 'react';
import { View, ActivityIndicator } from 'react-native';
import { Stack, Redirect, usePathname, router, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { ShareIntentProvider, useShareIntentContext } from 'expo-share-intent';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider, useSafeAreaInsets } from 'react-native-safe-area-context';
import Toast from 'react-native-toast-message';
import { createApiClient, setDefaultApiClient } from '@music-minion/shared';
import { hydrateStorage } from '../stores/playerStore';
import { useServerUrl } from '../hooks/useServerUrl';
import { useSyncWebSocket } from '../hooks/useSyncWebSocket';
import { PlayerBar } from '../components/player/PlayerBar';
import { ConnectionStatus } from '../components/ConnectionStatus';
import { ConnectionStatusContext } from '../hooks/useConnectionStatus';
import '../global.css';
import { verifyInstallation } from 'nativewind';

if (__DEV__) {
  verifyInstallation();
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 30_000,
    },
  },
});

function AppContent() {
  const { serverUrl, isConfigured, isLoading } = useServerUrl();
  const pathname = usePathname();
  const { hasShareIntent } = useShareIntentContext();
  // Edge-to-edge Android draws under the status bar. Inset every screen once
  // here so scroll content clips below the status bar instead of behind it.
  // Screens add no top padding of their own: ScreenHeader owns that spacing.
  const { top: topInset } = useSafeAreaInsets();

  // Init API client when server URL is available
  useEffect(() => {
    if (serverUrl) {
      const client = createApiClient(serverUrl);
      setDefaultApiClient(client);
    }
  }, [serverUrl]);

  // Route shared URLs to the settings screen. Works on cold start because the
  // ShareIntentProvider is always mounted at the root layout.
  useEffect(() => {
    if (hasShareIntent && isConfigured) {
      router.push('/settings');
    }
  }, [hasShareIntent, isConfigured]);

  // WebSocket sync for player + device state
  const { status, retry } = useSyncWebSocket({ serverUrl });
  const connection = useMemo(() => ({ status, retry }), [status, retry]);

  if (isLoading) {
    return (
      <View style={{ flex: 1, backgroundColor: '#121212', justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator color="#7C4DFF" />
      </View>
    );
  }

  if (!isConfigured && pathname !== '/setup') {
    return <Redirect href="/setup" />;
  }

  return (
    <ConnectionStatusContext.Provider value={connection}>
      <View style={{ flex: 1, backgroundColor: '#121212', paddingTop: topInset }}>
        <Stack screenOptions={{ headerShown: false }}>
          <Stack.Screen name="setup" />
          <Stack.Screen name="(main)" />
        </Stack>
        <ConnectionStatus status={status} retry={retry} />
        {isConfigured && <PlayerBar />}
      </View>
    </ConnectionStatusContext.Provider>
  );
}

export default function RootLayout() {
  const appRouter = useRouter();
  const [isHydrated, setIsHydrated] = useState(false);

  // Hydrate persisted store values (device ID, volume, mute, shuffle) from
  // AsyncStorage BEFORE mounting AppContent — useSyncWebSocket sends
  // device:register with thisDeviceId, which must be the persisted ID.
  useEffect(() => {
    let cancelled = false;
    hydrateStorage()
      .catch(() => undefined) // AsyncStorage failure: proceed with in-memory defaults
      .then(() => {
        if (!cancelled) setIsHydrated(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!isHydrated) {
    return (
      <View style={{ flex: 1, backgroundColor: '#121212', justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator color="#7C4DFF" />
      </View>
    );
  }

  return (
    <ShareIntentProvider
      options={{
        debug: __DEV__,
        resetOnBackground: true,
        onResetShareIntent: () => appRouter.replace('/'),
      }}
    >
      <GestureHandlerRootView style={{ flex: 1 }}>
        <SafeAreaProvider>
          <QueryClientProvider client={queryClient}>
            <StatusBar style="light" />
            <AppContent />
            <Toast />
          </QueryClientProvider>
        </SafeAreaProvider>
      </GestureHandlerRootView>
    </ShareIntentProvider>
  );
}
