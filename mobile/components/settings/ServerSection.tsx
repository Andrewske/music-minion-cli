/**
 * Settings > Server: collapsed by default to one row (host + chevron);
 * expands to the raw URL field and Save & Test.
 */
import { useState } from 'react';
import type { ReactElement } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { ChevronDown, ChevronUp, Server } from 'lucide-react-native';
import { healthUrl, serverHost } from '../../features/settings/connectionHealth';

type SaveStatus = 'idle' | 'success' | 'error';

interface ServerSectionProps {
  serverUrl: string | null;
  saveServerUrl: (url: string) => Promise<void>;
  onSaved: () => void;
}

async function urlIsHealthy(url: string): Promise<boolean> {
  try {
    const response = await fetch(healthUrl(url), { signal: AbortSignal.timeout(5000) });
    return response.ok;
  } catch {
    return false;
  }
}

export function ServerSection({ serverUrl, saveServerUrl, onSaved }: ServerSectionProps): ReactElement {
  const [open, setOpen] = useState(false);
  const Chevron = open ? ChevronUp : ChevronDown;
  return (
    <View style={styles.section}>
      <Pressable
        style={styles.toggle}
        onPress={() => setOpen((v) => !v)}
        accessibilityRole="button"
        accessibilityState={{ expanded: open }}
        testID="settings-server-toggle"
        android_ripple={{ color: '#FFFFFF14' }}
      >
        <Server size={20} color="#9E9E9E" />
        <View style={styles.toggleText}>
          <Text style={styles.toggleTitle}>Server</Text>
          <Text style={styles.toggleHost} numberOfLines={1}>{serverUrl ? serverHost(serverUrl) : 'Not set'}</Text>
        </View>
        <Chevron size={20} color="#9E9E9E" />
      </Pressable>
      {open ? <ServerForm initialUrl={serverUrl ?? ''} saveServerUrl={saveServerUrl} onSaved={onSaved} /> : null}
    </View>
  );
}

interface ServerFormProps {
  initialUrl: string;
  saveServerUrl: (url: string) => Promise<void>;
  onSaved: () => void;
}

function useTestAndSave(saveServerUrl: (url: string) => Promise<void>, onSaved: () => void): { testing: boolean; status: SaveStatus; run: (url: string) => Promise<void> } {
  const [testing, setTesting] = useState(false);
  const [status, setStatus] = useState<SaveStatus>('idle');
  const run = async (url: string): Promise<void> => {
    setTesting(true);
    setStatus('idle');
    try {
      const ok = await urlIsHealthy(url);
      if (ok) await saveServerUrl(url);
      setStatus(ok ? 'success' : 'error');
      if (ok) onSaved();
    } catch {
      setStatus('error');
    } finally {
      setTesting(false);
    }
  };
  return { testing, status, run };
}

function ServerForm({ initialUrl, saveServerUrl, onSaved }: ServerFormProps): ReactElement {
  const [url, setUrl] = useState(initialUrl);
  const { testing, status, run } = useTestAndSave(saveServerUrl, onSaved);
  return (
    <View style={styles.form}>
      <Text className="text-text-secondary text-sm mb-2">Server URL</Text>
      <TextInput
        testID="settings-server-url"
        className="bg-surface text-text-primary rounded-lg px-4 py-3 text-base border border-neutral-700 mb-3"
        value={url}
        onChangeText={setUrl}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
      />
      <Pressable className="bg-primary rounded-lg py-3 items-center mb-2" onPress={() => run(url)} disabled={testing}>
        {testing ? <ActivityIndicator color="#fff" /> : <Text className="text-white font-semibold">Save & Test</Text>}
      </Pressable>
      <SaveFeedback status={status} />
    </View>
  );
}

function SaveFeedback({ status }: { status: SaveStatus }): ReactElement | null {
  if (status === 'success') return <Text className="text-success text-sm">Connected and saved</Text>;
  if (status === 'error') return <Text className="text-error text-sm">Couldn&apos;t reach that server. Check the URL and try again.</Text>;
  return null;
}

const styles = StyleSheet.create({
  section: {
    marginTop: 16,
    backgroundColor: '#1A1A1A',
    borderRadius: 14,
    overflow: 'hidden',
  },
  toggle: { flexDirection: 'row', alignItems: 'center', gap: 14, minHeight: 60, paddingHorizontal: 16 },
  toggleText: { flex: 1 },
  toggleTitle: { color: '#E0E0E0', fontSize: 15, fontWeight: '500' },
  toggleHost: { color: '#9E9E9E', fontSize: 12, marginTop: 1 },
  form: { paddingHorizontal: 16, paddingBottom: 16, paddingTop: 4 },
});
