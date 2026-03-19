/**
 * Settings — server URL config, import from shared URLs.
 */
import {
  View,
  Text,
  TextInput,
  Pressable,
  ActivityIndicator,
  ScrollView,
} from 'react-native';
import { useState, useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import Toast from 'react-native-toast-message';
import { useServerUrl } from '../../hooks/useServerUrl';
import { useShareIntent } from '../../hooks/useShareIntent';
import { getDefaultApiClient } from '@music-minion/shared';

export default function SettingsScreen() {
  const { serverUrl, saveServerUrl } = useServerUrl();
  const { pendingUrl, clearPendingUrl } = useShareIntent();
  const queryClient = useQueryClient();
  const [url, setUrl] = useState(serverUrl ?? '');
  const [testing, setTesting] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');

  // Import state
  const [importUrl, setImportUrl] = useState('');
  const [importing, setImporting] = useState(false);

  // Pre-fill import URL from share intent
  useEffect(() => {
    if (pendingUrl) {
      setImportUrl(pendingUrl);
      clearPendingUrl();
    }
  }, [pendingUrl, clearPendingUrl]);

  const testAndSave = async () => {
    setTesting(true);
    setStatus('idle');
    try {
      const healthUrl = url.replace(/\/api$/, '/health');
      const response = await fetch(healthUrl, {
        signal: AbortSignal.timeout(5000),
      });
      if (response.ok) {
        await saveServerUrl(url);
        setStatus('success');
      } else {
        setStatus('error');
      }
    } catch {
      setStatus('error');
    } finally {
      setTesting(false);
    }
  };

  const handleImport = async () => {
    const trimmed = importUrl.trim();
    if (!trimmed) return;

    setImporting(true);
    try {
      const client = getDefaultApiClient();
      // Detect platform from URL
      if (trimmed.includes('youtube.com') || trimmed.includes('youtu.be')) {
        await client.post('/youtube/import', { url: trimmed });
      } else if (trimmed.includes('soundcloud.com')) {
        await client.post('/soundcloud/import', { url: trimmed });
      } else {
        Toast.show({ type: 'error', text1: 'Unsupported URL', text2: 'Only YouTube and SoundCloud URLs are supported' });
        setImporting(false);
        return;
      }

      Toast.show({ type: 'success', text1: 'Imported!', text2: trimmed });
      setImportUrl('');
      queryClient.invalidateQueries({ queryKey: ['playlists'] });
    } catch (err) {
      Toast.show({
        type: 'error',
        text1: 'Import failed',
        text2: err instanceof Error ? err.message : 'Unknown error',
      });
    } finally {
      setImporting(false);
    }
  };

  return (
    <ScrollView className="flex-1 bg-background" contentContainerStyle={{ paddingBottom: 80 }}>
      <View className="px-4 pt-12">
        <Text className="text-text-primary text-2xl font-bold mb-6">
          Settings
        </Text>

        {/* Server URL */}
        <Text className="text-text-secondary text-sm mb-2">Server URL</Text>
        <TextInput
          className="bg-surface text-text-primary rounded-lg px-4 py-3 text-base border border-neutral-700 mb-3"
          value={url}
          onChangeText={setUrl}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="url"
        />

        <Pressable
          className="bg-primary rounded-lg py-3 items-center mb-2"
          onPress={testAndSave}
          disabled={testing}
        >
          {testing ? (
            <ActivityIndicator color="#fff" />
          ) : (
            <Text className="text-white font-semibold">Save & Test</Text>
          )}
        </Pressable>

        {status === 'success' && (
          <Text className="text-success text-sm mb-4">Connected!</Text>
        )}
        {status === 'error' && (
          <Text className="text-error text-sm mb-4">Connection failed</Text>
        )}

        {/* Import section */}
        <View className="mt-8 pt-6 border-t border-neutral-800">
          <Text className="text-text-primary text-lg font-bold mb-2">
            Import
          </Text>
          <Text className="text-text-secondary text-sm mb-3">
            Paste a YouTube or SoundCloud URL to import
          </Text>

          <TextInput
            className="bg-surface text-text-primary rounded-lg px-4 py-3 text-base border border-neutral-700 mb-3"
            placeholder="https://youtube.com/watch?v=..."
            placeholderTextColor="#666"
            value={importUrl}
            onChangeText={setImportUrl}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="url"
          />

          <Pressable
            className="bg-surface rounded-lg py-3 items-center border border-primary"
            onPress={handleImport}
            disabled={importing || !importUrl.trim()}
          >
            {importing ? (
              <ActivityIndicator color="#7C4DFF" />
            ) : (
              <Text className="text-primary font-semibold">Import URL</Text>
            )}
          </Pressable>
        </View>

        {/* App info */}
        <View className="mt-8">
          <Text className="text-text-secondary text-xs">
            Music Minion Mobile v0.0.1
          </Text>
          <Text className="text-text-secondary text-xs mt-1">
            Share a URL from any app to import tracks
          </Text>
        </View>
      </View>
    </ScrollView>
  );
}
