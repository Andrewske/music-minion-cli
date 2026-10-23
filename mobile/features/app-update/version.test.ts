import { describe, expect, it } from 'vitest';
import {
  compareVersions,
  formatMegabytes,
  parseInstalledVersion,
  parseLatestBuild,
  type LatestBuild,
} from './version';

const latest = (versionCode: number): LatestBuild => ({
  versionCode,
  versionName: `1.${versionCode}+abc1234`,
  sha: 'abc1234',
  builtAt: '2026-10-23T12:00:00Z',
  apkSize: 100_000_000,
  changelog: ['feat(mobile): updates'],
});

describe('parseLatestBuild', () => {
  it('maps a valid manifest', () => {
    expect(
      parseLatestBuild({
        versionCode: 812,
        versionName: '1.812+abc1234',
        sha: 'abc1234',
        built_at: '2026-10-23T12:00:00Z',
        apk_size: 100_000_000,
        changelog: ['feat(mobile): updates', 7],
      }),
    ).toEqual(latest(812));
  });

  it('rejects malformed manifests', () => {
    expect(parseLatestBuild(null)).toBeNull();
    expect(parseLatestBuild([])).toBeNull();
    expect(parseLatestBuild({ versionCode: '812', versionName: 'x', sha: 'y' })).toBeNull();
    expect(parseLatestBuild({ versionCode: 0, versionName: 'x', sha: 'y' })).toBeNull();
    expect(parseLatestBuild({ versionCode: 3, sha: 'y' })).toBeNull();
  });

  it('defaults optional fields', () => {
    expect(parseLatestBuild({ versionCode: 3, versionName: 'x', sha: 'y' })).toEqual({
      versionCode: 3,
      versionName: 'x',
      sha: 'y',
      builtAt: '',
      apkSize: null,
      changelog: [],
    });
  });
});

describe('parseInstalledVersion', () => {
  it('splits label and sha', () => {
    expect(parseInstalledVersion('1.812+abc1234', '812')).toEqual({
      versionCode: 812,
      label: '1.812',
      sha: 'abc1234',
    });
  });

  it('handles legacy and missing values', () => {
    expect(parseInstalledVersion('0.0.1', '1')).toEqual({ versionCode: 1, label: '0.0.1', sha: null });
    expect(parseInstalledVersion(null, null)).toEqual({ versionCode: null, label: 'unknown', sha: null });
  });
});

describe('compareVersions', () => {
  it('is up to date when installed is the same or newer', () => {
    expect(compareVersions(812, latest(812))).toEqual({ kind: 'up-to-date' });
    expect(compareVersions(900, latest(812))).toEqual({ kind: 'up-to-date' });
  });

  it('counts commits behind', () => {
    expect(compareVersions(800, latest(812))).toEqual({
      kind: 'available',
      latest: latest(812),
      commitsBehind: 12,
    });
  });

  it('offers the update when the installed code is unknown', () => {
    expect(compareVersions(null, latest(812))).toMatchObject({ kind: 'available', commitsBehind: 0 });
  });
});

describe('formatMegabytes', () => {
  it('formats or passes null through', () => {
    expect(formatMegabytes(104_857_600)).toBe('105 MB');
    expect(formatMegabytes(null)).toBeNull();
  });
});
