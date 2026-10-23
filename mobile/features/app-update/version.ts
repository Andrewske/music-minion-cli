/**
 * Pure version logic for the in-app updater. versionCode is the git commit
 * count, so the difference between two codes is the number of commits behind.
 */

export interface LatestBuild {
  versionCode: number;
  versionName: string;
  sha: string;
  builtAt: string;
  apkSize: number | null;
  changelog: string[];
}

export interface InstalledVersion {
  versionCode: number | null;
  label: string;
  sha: string | null;
}

export type UpdateStatus =
  | { kind: 'up-to-date' }
  | { kind: 'available'; latest: LatestBuild; commitsBehind: number };

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const isPositiveInt = (value: unknown): value is number =>
  typeof value === 'number' && Number.isInteger(value) && value > 0;

/** Validates the backend's latest.json; null when it's malformed. */
export const parseLatestBuild = (raw: unknown): LatestBuild | null => {
  if (!isRecord(raw)) return null;
  const { versionCode, versionName, sha, built_at, apk_size, changelog } = raw;
  if (!isPositiveInt(versionCode)) return null;
  if (typeof versionName !== 'string' || typeof sha !== 'string') return null;
  return {
    versionCode,
    versionName,
    sha,
    builtAt: typeof built_at === 'string' ? built_at : '',
    apkSize: isPositiveInt(apk_size) ? apk_size : null,
    changelog: Array.isArray(changelog)
      ? changelog.filter((line): line is string => typeof line === 'string')
      : [],
  };
};

/** Splits native versionName "1.812+abc1234" into a label and sha. */
export const parseInstalledVersion = (
  versionName: string | null,
  buildVersion: string | null,
): InstalledVersion => {
  const parsedCode = Number.parseInt(buildVersion ?? '', 10);
  const versionCode = isPositiveInt(parsedCode) ? parsedCode : null;
  const [label, sha] = (versionName ?? 'unknown').split('+', 2);
  return { versionCode, label: label || 'unknown', sha: sha ?? null };
};

/** Unknown installed code counts as outdated so a fix can always be installed. */
export const compareVersions = (
  installedCode: number | null,
  latest: LatestBuild,
): UpdateStatus => {
  if (installedCode !== null && latest.versionCode <= installedCode) {
    return { kind: 'up-to-date' };
  }
  const commitsBehind = installedCode === null ? 0 : latest.versionCode - installedCode;
  return { kind: 'available', latest, commitsBehind };
};

export const formatMegabytes = (bytes: number | null): string | null =>
  bytes === null ? null : `${(bytes / 1_000_000).toFixed(0)} MB`;
