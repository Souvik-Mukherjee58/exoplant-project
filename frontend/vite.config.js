import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// On Vercel the app is static: a relative '/api/v1' would hit Vercel itself (rewritten to index.html)
// and every API call would return HTML. Fail the build instead of shipping a broken site.
if (process.env.VERCEL && !process.env.VITE_API_URL) {
  throw new Error(
    'VITE_API_URL must be set for Vercel builds, e.g. https://<your-backend>.fly.dev/api/v1'
  );
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
  },
});
