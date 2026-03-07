import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    // Prevent Vite from pre-bundling pdfjs-dist — it must stay as-is
    // because it uses dynamic imports internally for the worker
    exclude: ['pdfjs-dist'],
  },
  build: {
    rollupOptions: {
      output: {
        // Keep pdfjs in its own chunk so the worker URL stays resolvable
        manualChunks(id) {
          if (id.includes('pdfjs-dist')) {
            return 'pdfjs';
          }
        },
      },
    },
  },
});