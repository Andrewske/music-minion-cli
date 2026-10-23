/**
 * Native side of the updater: read the installed version, download the APK,
 * hand it to the Android package installer.
 */
import * as Application from 'expo-application';
import { File, Paths } from 'expo-file-system';
import * as IntentLauncher from 'expo-intent-launcher';
import { getDefaultApiClient } from '@music-minion/shared';
import { parseInstalledVersion, parseLatestBuild, type InstalledVersion, type LatestBuild } from './version';

const APK_MIME = 'application/vnd.android.package-archive';
const CACHE_APK_NAME = 'music-minion-update.apk';
// Intent.FLAG_GRANT_READ_URI_PERMISSION: lets the installer read our content URI.
const FLAG_GRANT_READ_URI_PERMISSION = 1;

export const getInstalledVersion = (): InstalledVersion =>
  parseInstalledVersion(Application.nativeApplicationVersion, Application.nativeBuildVersion);

/** null when the backend has no build published yet (404). */
export const fetchLatestBuild = async (): Promise<LatestBuild | null> => {
  const client = getDefaultApiClient();
  const response = await fetch(`${client.getBaseUrl()}/app/latest`, {
    signal: AbortSignal.timeout(10_000),
  });
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`GET /app/latest failed: HTTP ${response.status}`);
  const latest = parseLatestBuild(await response.json());
  if (!latest) throw new Error('GET /app/latest returned a malformed manifest');
  return latest;
};

/** Native download straight to the cache dir; the APK never sits in JS memory. */
export const downloadApk = async (): Promise<File> => {
  const url = `${getDefaultApiClient().getBaseUrl()}/app/apk`;
  const destination = new File(Paths.cache, CACHE_APK_NAME);
  return File.downloadFileAsync(url, destination, { idempotent: true });
};

/**
 * Opens the system installer. If "install unknown apps" isn't granted yet,
 * Android shows its own prompt with a shortcut to the setting.
 */
export const launchInstaller = async (apk: File): Promise<void> => {
  await IntentLauncher.startActivityAsync('android.intent.action.VIEW', {
    data: apk.contentUri,
    type: APK_MIME,
    flags: FLAG_GRANT_READ_URI_PERMISSION,
  });
};

/** Opens Settings > "Install unknown apps" for this app. */
export const openInstallPermissionSettings = async (): Promise<void> => {
  await IntentLauncher.startActivityAsync(IntentLauncher.ActivityAction.MANAGE_UNKNOWN_APP_SOURCES, {
    data: `package:${Application.applicationId ?? 'com.musicminion.app'}`,
  });
};
