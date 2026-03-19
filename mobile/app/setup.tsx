/**
 * First-run setup — configure Tailscale server URL.
 */
import { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  Pressable,
  ActivityIndicator,
} from 'react-native';
import { router } from 'expo-router';
import { useServerUrl } from '../hooks/useServerUrl';

export default function SetupScreen() {
  const { saveServerUrl } = useServerUrl();
  const [url, setUrl] = useState('');
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const testConnection = async () => {
    const trimmed = url.trim().replace(/\/+$/, '');
    if (!trimmed) {
      setError('Enter a server URL');
      return;
    }

    const apiUrl = trimmed.includes('/api') ? trimmed : `${trimmed}/api`;

    setTesting(true);
    setError(null);
    setSuccess(false);

    try {
      const healthUrl = apiUrl.replace(/\/api$/, '/health');
      const response = await fetch(healthUrl, {
        signal: AbortSignal.timeout(5000),
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      const data = await response.json();
      if (data.status === 'healthy') {
        setSuccess(true);
        await saveServerUrl(apiUrl);
        setTimeout(() => router.replace('/(tabs)'), 800);
      } else {
        throw new Error('Unexpected response');
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'TimeoutError') {
        setError("Can't reach server — is Tailscale running?");
      } else {
        setError(err instanceof Error ? err.message : 'Connection failed');
      }
    } finally {
      setTesting(false);
    }
  };

  return (
    <View className="flex-1 bg-background justify-center px-6">
      <Text className="text-text-primary text-3xl font-bold mb-2">
        Music Minion
      </Text>
      <Text className="text-text-secondary text-base mb-8">
        Connect to your server over Tailscale
      </Text>

      <Text className="text-text-secondary text-sm mb-2">Server URL</Text>
      <TextInput
        className="bg-surface text-text-primary rounded-lg px-4 py-3 text-base border border-neutral-700 mb-4"
        placeholder="my-server.tailnet.ts.net:8642"
        placeholderTextColor="#666"
        value={url}
        onChangeText={setUrl}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        returnKeyType="go"
        onSubmitEditing={testConnection}
      />

      {error && (
        <View className="bg-red-900/30 rounded-lg px-4 py-3 mb-4">
          <Text className="text-error text-sm">{error}</Text>
        </View>
      )}

      {success && (
        <View className="bg-green-900/30 rounded-lg px-4 py-3 mb-4">
          <Text className="text-success text-sm">Connected!</Text>
        </View>
      )}

      <Pressable
        className="bg-primary rounded-lg py-4 items-center"
        onPress={testConnection}
        disabled={testing}
      >
        {testing ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text className="text-white text-base font-semibold">
            Test Connection
          </Text>
        )}
      </Pressable>
    </View>
  );
}
