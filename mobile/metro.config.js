/**
 * Metro config for monorepo — resolves @music-minion/shared
 * from the workspace root.
 *
 * Without this, Metro can't find packages outside mobile/.
 */
const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

const projectRoot = __dirname;
const sharedDir = path.resolve(projectRoot, '../shared');
const workspaceRoot = path.resolve(projectRoot, '..');

const config = getDefaultConfig(projectRoot);

// Watch the shared package for changes
config.watchFolders = [sharedDir];

// Resolve modules from both mobile/node_modules and root/node_modules
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, 'node_modules'),
  path.resolve(workspaceRoot, 'node_modules'),
];

// Ensure Metro doesn't duplicate React/React Native from shared
config.resolver.disableHierarchicalLookup = true;

module.exports = config;
