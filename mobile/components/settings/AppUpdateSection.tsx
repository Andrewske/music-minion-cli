/**
 * Settings > App updates: installed version, check for a newer APK on the
 * server, download it and open the Android installer.
 */
import { ActivityIndicator, Pressable, Text, View } from 'react-native';
import type { ReactElement } from 'react';
import { openInstallPermissionSettings } from '../../features/app-update/installer';
import { useAppUpdate, type UpdatePhase } from '../../features/app-update/useAppUpdate';
import { formatMegabytes, type LatestBuild } from '../../features/app-update/version';

const MAX_CHANGELOG_LINES = 15;

const describeUpdate = (latest: LatestBuild, commitsBehind: number): string => {
  const commits = commitsBehind > 0 ? ` (${commitsBehind} commit${commitsBehind === 1 ? '' : 's'})` : '';
  return `Update to ${latest.versionName}${commits}`;
};

const Changelog = ({ lines }: { lines: string[] }): ReactElement | null => {
  if (lines.length === 0) return null;
  const hidden = lines.length - MAX_CHANGELOG_LINES;
  return (
    <View className="mb-3">
      {lines.slice(0, MAX_CHANGELOG_LINES).map((line, i) => (
        <Text key={`${i}-${line}`} className="text-text-secondary text-xs mb-1">
          • {line}
        </Text>
      ))}
      {hidden > 0 && <Text className="text-text-secondary text-xs">…and {hidden} more</Text>}
    </View>
  );
};

const PermissionHint = (): ReactElement => (
  <Pressable onPress={openInstallPermissionSettings} className="mt-2">
    <Text className="text-text-secondary text-xs">
      Android blocked it? Tap to allow installs from Music Minion, then tap Install again.
    </Text>
  </Pressable>
);

const UpdateDetails = ({ phase, onInstall }: { phase: UpdatePhase; onInstall: () => void }): ReactElement | null => {
  if (phase.kind === 'none-published') {
    return <Text className="text-text-secondary text-sm mb-3">No build published on the server yet</Text>;
  }
  const status = 'status' in phase ? phase.status : null;
  if (status?.kind === 'up-to-date') {
    return <Text className="text-success text-sm mb-3">Up to date</Text>;
  }
  if (status?.kind !== 'available') return null;
  const downloading = phase.kind === 'downloading';
  const size = formatMegabytes(status.latest.apkSize);
  return (
    <View className="mb-3">
      <Text className="text-text-primary text-sm font-semibold mb-2">
        {describeUpdate(status.latest, status.commitsBehind)}
      </Text>
      <Changelog lines={status.latest.changelog} />
      <Pressable className="bg-primary rounded-lg py-3 items-center" onPress={onInstall} disabled={downloading}>
        {downloading ? (
          <Text className="text-white font-semibold">Downloading{size ? ` ${size}` : ''}…</Text>
        ) : (
          <Text className="text-white font-semibold">Install</Text>
        )}
      </Pressable>
      {(phase.kind === 'installer-opened' || phase.kind === 'error') && <PermissionHint />}
    </View>
  );
};

export function AppUpdateSection(): ReactElement {
  const { installed, phase, check, install } = useAppUpdate();
  const checking = phase.kind === 'checking';
  return (
    <View className="mt-8 pt-6 border-t border-neutral-800">
      <Text className="text-text-primary text-lg font-bold mb-2">App updates</Text>
      <Text className="text-text-secondary text-sm mb-3">
        Installed v{installed.label}
        {installed.sha ? ` (${installed.sha})` : ''}
      </Text>
      {phase.kind === 'error' && <Text className="text-error text-sm mb-3">{phase.message}</Text>}
      <UpdateDetails phase={phase} onInstall={install} />
      <Pressable
        className="bg-surface rounded-lg py-3 items-center border border-primary"
        onPress={check}
        disabled={checking || phase.kind === 'downloading'}
      >
        {checking ? (
          <ActivityIndicator color="#7C4DFF" />
        ) : (
          <Text className="text-primary font-semibold">Check for updates</Text>
        )}
      </Pressable>
    </View>
  );
}
