import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const here = path.dirname(fileURLToPath(import.meta.url));
const apiTypes = path.resolve(here, '../../packages/api-types/src/index.ts');

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@api-types': apiTypes } },
  server: { port: 5173, fs: { allow: [path.resolve(here, '../..')] } },
});
