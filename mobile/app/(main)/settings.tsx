/**
 * Settings — connection status + latency up top, then the collapsible Server
 * section (raw URL), Import (also the share-intent landing spot) and updates.
 */
import type { ReactElement } from 'react';
import { ScrollView, View } from 'react-native';
import { RefreshCw } from 'lucide-react-native';
import { useServerUrl } from '../../hooks/useServerUrl';
import { useConnectionStatus } from '../../hooks/useConnectionStatus';
import { useServerLatency } from '../../hooks/useServerLatency';
import { AppUpdateSection } from '../../components/settings/AppUpdateSection';
import { ConnectionCard } from '../../components/settings/ConnectionCard';
import { ImportSection } from '../../components/settings/ImportSection';
import { ServerSection } from '../../components/settings/ServerSection';
import { HeaderIconButton, ScreenHeader } from '../../components/ScreenHeader';

export default function SettingsScreen(): ReactElement {
  const { serverUrl, saveServerUrl } = useServerUrl();
  const { status, retry } = useConnectionStatus();
  const { reading, refresh } = useServerLatency(serverUrl);
  const reconnect = (): void => {
    retry();
    refresh();
  };

  return (
    <View className="flex-1 bg-background">
      <ScreenHeader
        title="Settings"
        right={<HeaderIconButton icon={RefreshCw} label="Check connection" onPress={refresh} testID="settings-recheck" />}
      />
      <ScrollView className="flex-1" contentContainerStyle={{ paddingBottom: 80 }} keyboardShouldPersistTaps="handled">
        <View className="px-4 pt-2">
          <ConnectionCard serverUrl={serverUrl} wsStatus={status} reading={reading} onReconnect={reconnect} />
          <ServerSection serverUrl={serverUrl} saveServerUrl={saveServerUrl} onSaved={reconnect} />
          <ImportSection />
          <AppUpdateSection />
        </View>
      </ScrollView>
    </View>
  );
}
