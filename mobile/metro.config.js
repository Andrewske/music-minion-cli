const { getDefaultConfig } = require('expo/metro-config');
const { withNativeWind } = require('nativewind/metro');
const path = require('path');

const projectRoot = __dirname;
const monorepoRoot = path.resolve(projectRoot, '..');
const mobileModules = path.resolve(projectRoot, 'node_modules');

const config = getDefaultConfig(projectRoot);

// Watch entire monorepo root (Expo-recommended for workspaces)
config.watchFolders = [monorepoRoot];

// Resolve from both mobile and root node_modules
config.resolver.nodeModulesPaths = [
  mobileModules,
  path.resolve(monorepoRoot, 'node_modules'),
];

// Force single copies of React/RN from mobile's node_modules
// (prevents version mismatch with root-hoisted copies)
config.resolver.extraNodeModules = {
  'react': path.resolve(mobileModules, 'react'),
  'react-native': path.resolve(mobileModules, 'react-native'),
  'react-dom': path.resolve(mobileModules, 'react-dom'),
};

module.exports = withNativeWind(config, { input: './global.css' });
