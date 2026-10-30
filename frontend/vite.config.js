import { defineConfig } from 'vite';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('.', import.meta.url));
export default defineConfig({
  root,
  esbuild: { jsx: 'automatic' },
  plugins: [{
    name: 'xanh24-page-routes',
    configureServer(server) {
      server.middlewares.use((request, _response, next) => {
        const path = request.url?.split('?')[0];
        if (path === '/admin' || path === '/admin/' || path === '/download' || path === '/download/' || path?.startsWith('/go/')) {
          request.url = request.url.replace(path, '/index.html');
        }
        next();
      });
    },
  }],
  build: {
    outDir: resolve(root, 'dist'),
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      ['/api', '/uploads', '/vendor', '/assets', '/sw.js', '/manifest.webmanifest', '/modules'].map(path => [path, 'http://127.0.0.1:8024']),
    ),
  },
});
