module.exports = function (api) {
  api.cache(true);
  return {
    presets: [
      ['babel-preset-expo', { jsxImportSource: 'nativewind' }],
    ],
    plugins: [
      // Inlined from nativewind/babel → react-native-css-interop/babel,
      // excluding the broken "react-native-worklets/plugin" reference
      // (that plugin is for Reanimated 4+, we're on 3.16.x)
      require('react-native-css-interop/dist/babel-plugin').default,
      [
        '@babel/plugin-transform-react-jsx',
        {
          runtime: 'automatic',
          importSource: 'react-native-css-interop',
        },
      ],
      'react-native-reanimated/plugin', // Must be last
    ],
  };
};
