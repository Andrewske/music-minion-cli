/**
 * Root layout — providers, API client init, WebSocket sync, PlayerBar.
 */
import { useEffect } from 'react';
import { View, ActivityIndicator } from 'react-native';
import { Stack, Redirect, usePathname } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import Toast from 'react-native-toast-message';
import { createApiClient, setDefaultApiClient } from '@music-minion/shared';
import { useServerUrl } from '../hooks/useServerUrl';
import { useSyncWebSocket } from '../hooks/useSyncWebSocket';
import { PlayerBar } from '../components/player/PlayerBar';
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

  // Init API client when server URL is available
  useEffect(() => {
    if (serverUrl) {
      const client = createApiClient(serverUrl);
      setDefaultApiClient(client);
    }
  }, [serverUrl]);

  // WebSocket sync for player + device state
  useSyncWebSocket({ serverUrl });

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
      {isConfigured && <PlayerBar />}
    </View>
  );
}

export default function RootLayout() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <QueryClientProvider client={queryClient}>
          <StatusBar style="light" />
          <AppContent />
          <Toast />
        </QueryClientProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
