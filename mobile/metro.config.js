const { getDefaultConfig } = require('expo/metro-config');
const { withNativeWind } = require('nativewind/metro');
const path = require('path');

const projectRoot = __dirname;
const monorepoRoot = path.resolve(projectRoot, '..');
const mobileModules = path.resolve(projectRoot, 'node_modules');
const rootModules = path.resolve(monorepoRoot, 'node_modules');

const config = getDefaultConfig(projectRoot);

config.watchFolders = [monorepoRoot];

config.resolver.nodeModulesPaths = [
  mobileModules,
  rootModules,
];

config.resolver.extraNodeModules = {
  'react': path.resolve(rootModules, 'react'),
  'react-native': path.resolve(rootModules, 'react-native'),
  'react-dom': path.resolve(rootModules, 'react-dom'),
};

module.exports = withNativeWind(config, { input: './global.css' });
