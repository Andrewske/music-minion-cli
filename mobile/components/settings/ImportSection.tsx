/**
 * Settings > Import: paste (or share into the app) a YouTube / SoundCloud URL.
 * A URL shared from another app lands here pre-filled: the root layout routes
 * the share intent to /settings and useShareIntent hands over the URL.
 */
import { useEffect, useState } from 'react';
import type { ReactElement } from 'react';
import { ActivityIndicator, Pressable, Text, TextInput, View } from 'react-native';
import { useQueryClient } from '@tanstack/react-query';
import Toast from 'react-native-toast-message';
import { getDefaultApiClient } from '@music-minion/shared';
import { useShareIntent } from '../../hooks/useShareIntent';
import { importEndpoint } from '../../features/settings/importUrl';

function useImport(): { importUrl: string; setImportUrl: (url: string) => void; importing: boolean; run: () => Promise<void> } {
  const queryClient = useQueryClient();
  const [importUrl, setImportUrl] = useState('');
  const [importing, setImporting] = useState(false);
  usePrefillFromShare(setImportUrl);

  const run = async (): Promise<void> => {
    const url = importUrl.trim();
    const endpoint = importEndpoint(url);
    if (!url) return;
    if (!endpoint) {
      Toast.show({ type: 'error', text1: 'Unsupported URL', text2: 'Only YouTube and SoundCloud URLs are supported' });
      return;
    }
    setImporting(true);
    await postImport(endpoint, url, () => {
      setImportUrl('');
      void queryClient.invalidateQueries({ queryKey: ['playlists'] });
    });
    setImporting(false);
  };
  return { importUrl, setImportUrl, importing, run };
}

/** Pre-fill the field from a URL shared into the app. */
function usePrefillFromShare(setImportUrl: (url: string) => void): void {
  const { pendingUrl, clearPendingUrl } = useShareIntent();
  useEffect(() => {
    if (!pendingUrl) return;
    setImportUrl(pendingUrl);
    clearPendingUrl();
  }, [pendingUrl, clearPendingUrl, setImportUrl]);
}

async function postImport(endpoint: string, url: string, onSuccess: () => void): Promise<void> {
  try {
    await getDefaultApiClient().post(endpoint, { url });
    Toast.show({ type: 'success', text1: 'Imported', text2: url });
    onSuccess();
  } catch (err) {
    Toast.show({ type: 'error', text1: 'Import failed', text2: err instanceof Error ? err.message : 'Unknown error' });
  }
}

export function ImportSection(): ReactElement {
  const { importUrl, setImportUrl, importing, run } = useImport();
  return (
    <View className="mt-8">
      <Text className="text-text-primary text-lg font-bold mb-1">Import</Text>
      <Text className="text-text-secondary text-sm mb-3">
        Paste a YouTube or SoundCloud URL, or share one to Music Minion from any app.
      </Text>
      <TextInput
        testID="settings-import-url"
        className="bg-surface text-text-primary rounded-lg px-4 py-3 text-base border border-neutral-700 mb-3"
        placeholder="https://soundcloud.com/..."
        placeholderTextColor="#666"
        value={importUrl}
        onChangeText={setImportUrl}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
      />
      <Pressable
        className="bg-surface rounded-lg py-3 items-center border border-primary"
        onPress={run}
        disabled={importing || !importUrl.trim()}
      >
        {importing ? <ActivityIndicator color="#7C4DFF" /> : <Text className="text-primary font-semibold">Import URL</Text>}
      </Pressable>
    </View>
  );
}
