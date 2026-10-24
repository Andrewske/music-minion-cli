// https://docs.expo.dev/guides/using-eslint/
const { defineConfig } = require('eslint/config');
const expoConfig = require('eslint-config-expo/flat');

module.exports = defineConfig([
  expoConfig,
  {
    // .maestro/scripts run in Maestro's JS sandbox (output, maestro, env globals).
    ignores: ['dist/*', 'android/*', '.expo/*', '.maestro/*'],
  },
]);
