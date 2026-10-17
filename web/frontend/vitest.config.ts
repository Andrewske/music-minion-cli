import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // react-dom lives in web/frontend/node_modules, not the hoisted root, so root-level
  // deps like @react-spring/web must be inlined and resolved from this package.
  resolve: { dedupe: ['react', 'react-dom'] },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    globals: true,
    server: { deps: { inline: [/@react-spring\//, /@radix-ui\//] } },
  },
});
