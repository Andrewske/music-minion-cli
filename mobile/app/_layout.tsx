/**
 * Root layout — providers, API client init, WebSocket sync, PlayerBar.
 */
import { useEffect } from 'react';
import { View, ActivityIndicator } from 'react-native';
import { Stack, Redirect, usePathname, router, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { ShareIntentProvider, useShareIntentContext } from 'expo-share-intent';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import Toast from 'react-native-toast-message';
import { createApiClient, setDefaultApiClient } from '@music-minion/shared';
import { useServerUrl } from '../hooks/useServerUrl';
import { useSyncWebSocket } from '../hooks/useSyncWebSocket';
import { PlayerBar } from '../components/player/PlayerBar';
import { ConnectionStatus } from '../components/ConnectionStatus';
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
      router.push('/(tabs)/settings');
    }
  }, [hasShareIntent, isConfigured]);

  // WebSocket sync for player + device state
  const { status, retry } = useSyncWebSocket({ serverUrl });

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
    <View style={{ flex: 1, backgroundColor: '#121212' }}>
      <Stack screenOptions={{ headerShown: false }}>
        <Stack.Screen name="setup" />
        <Stack.Screen name="(tabs)" />
      </Stack>
      <ConnectionStatus status={status} retry={retry} />
      {isConfigured && <PlayerBar />}
    </View>
  );
}

export default function RootLayout() {
  const appRouter = useRouter();
  return (
    <ShareIntentProvider
      options={{
        debug: __DEV__,
        resetOnBackground: true,
        onResetShareIntent: () => appRouter.replace('/(tabs)'),
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
