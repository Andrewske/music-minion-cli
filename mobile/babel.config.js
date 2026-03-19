module.exports = function (api) {
  api.cache(true);
  return {
    presets: [
      ['babel-preset-expo', { jsxImportSource: 'nativewind' }],
      'nativewind/babel',
    ],
    plugins: [
      [
        'module-resolver',
        {
          alias: {
            '@music-minion/shared': '../shared/src',
          },
        },
      ],
      'react-native-reanimated/plugin', // Must be last
    ],
  };
};
