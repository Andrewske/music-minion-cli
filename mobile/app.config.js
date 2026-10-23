// Layers build versioning on top of app.json so every APK is strictly newer.
//
// versionCode = git commit count on HEAD, versionName = "1.<count>+<sha>".
// scripts/build-apk.sh exports MM_VERSION_CODE / MM_VERSION_NAME; plain
// `expo run:android` builds fall back to asking git directly.
/* global __dirname */
const { execSync } = require('child_process');

const git = (args) => {
  try {
    return execSync(`git ${args}`, { cwd: __dirname, stdio: ['ignore', 'pipe', 'ignore'] })
      .toString()
      .trim();
  } catch {
    return null;
  }
};

const resolveVersion = () => {
  const envCode = Number.parseInt(process.env.MM_VERSION_CODE ?? '', 10);
  if (Number.isInteger(envCode) && envCode > 0 && process.env.MM_VERSION_NAME) {
    return { versionCode: envCode, versionName: process.env.MM_VERSION_NAME };
  }
  const count = Number.parseInt(git('rev-list --count HEAD') ?? '', 10);
  const sha = git('rev-parse --short HEAD') ?? 'unknown';
  const versionCode = Number.isInteger(count) && count > 0 ? count : 1;
  return { versionCode, versionName: `1.${versionCode}+${sha}` };
};

module.exports = ({ config }) => {
  const { versionCode, versionName } = resolveVersion();
  return {
    ...config,
    android: {
      ...config.android,
      versionCode,
      // android.version only sets versionName; expo.version (and with it the
      // appVersion runtimeVersion) stays fixed.
      version: versionName,
      permissions: [...(config.android?.permissions ?? []), 'android.permission.REQUEST_INSTALL_PACKAGES'],
    },
  };
};
