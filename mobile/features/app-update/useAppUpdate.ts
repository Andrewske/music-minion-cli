/**
 * State machine for Settings > App updates: check → (download → install).
 */
import { useCallback, useMemo, useState } from 'react';
import {
  downloadApk,
  fetchLatestBuild,
  getInstalledVersion,
  launchInstaller,
} from './installer';
import { compareVersions, type InstalledVersion, type UpdateStatus } from './version';

export type UpdatePhase =
  | { kind: 'idle' }
  | { kind: 'checking' }
  | { kind: 'none-published' }
  | { kind: 'checked'; status: UpdateStatus }
  | { kind: 'downloading'; status: UpdateStatus }
  | { kind: 'installer-opened'; status: UpdateStatus }
  | { kind: 'error'; message: string; status: UpdateStatus | null };

export interface AppUpdateState {
  installed: InstalledVersion;
  phase: UpdatePhase;
  check: () => Promise<void>;
  install: () => Promise<void>;
}

const errorMessage = (err: unknown): string => (err instanceof Error ? err.message : String(err));

const statusOf = (phase: UpdatePhase): UpdateStatus | null =>
  'status' in phase ? phase.status : null;

export const useAppUpdate = (): AppUpdateState => {
  const installed = useMemo(getInstalledVersion, []);
  const [phase, setPhase] = useState<UpdatePhase>({ kind: 'idle' });

  const check = useCallback(async (): Promise<void> => {
    setPhase({ kind: 'checking' });
    try {
      const latest = await fetchLatestBuild();
      setPhase(
        latest
          ? { kind: 'checked', status: compareVersions(installed.versionCode, latest) }
          : { kind: 'none-published' },
      );
    } catch (err) {
      setPhase({ kind: 'error', message: `Update check failed: ${errorMessage(err)}`, status: null });
    }
  }, [installed.versionCode]);

  const install = useCallback(async (): Promise<void> => {
    const status = statusOf(phase);
    if (status?.kind !== 'available') return;
    setPhase({ kind: 'downloading', status });
    try {
      const apk = await downloadApk();
      await launchInstaller(apk);
      setPhase({ kind: 'installer-opened', status });
    } catch (err) {
      setPhase({ kind: 'error', message: `Install failed: ${errorMessage(err)}`, status });
    }
  }, [phase]);

  return { installed, phase, check, install };
};
