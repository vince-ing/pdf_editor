import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { viteStaticCopy } from 'vite-plugin-static-copy'

// pdf.js 5.x loads three WASM binaries at runtime from inside the Web Worker:
//   openjpeg.wasm      — JPEG2000 decoder (used by textbook cover images)
//   jbig2.wasm         — JBIG2 decoder (used by scanned document images)
//   qcms_bg.wasm       — Color management / ICC profile handling
//
// These live in node_modules/pdfjs-dist/wasm/ and are fetched via fetch()
// inside pdf.worker.mjs at runtime. Vite does not copy these automatically,
// causing "JpxError: OpenJPEG failed to initialize" and blank image pages.

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),

    viteStaticCopy({
      targets: [
        // Worker script — referenced by workerSrc in App.tsx
        {
          src: 'node_modules/pdfjs-dist/build/pdf.worker.mjs',
          dest: 'pdfjs',
        },
        // WASM codecs — worker resolves these relative to its own URL,
        // so /pdfjs/wasm/ must mirror the node_modules/pdfjs-dist/wasm/ layout.
        {
          src: 'node_modules/pdfjs-dist/wasm/*',
          dest: 'pdfjs/wasm',
        },
        // cMaps — character maps for CJK and special-encoding PDFs
        {
          src: 'node_modules/pdfjs-dist/cmaps/*',
          dest: 'pdfjs/cmaps',
        },
        // Standard fonts — fallback when a PDF doesn't embed its own fonts
        {
          src: 'node_modules/pdfjs-dist/standard_fonts/*',
          dest: 'pdfjs/standard_fonts',
        },
      ],
    }),
  ],

  worker: {
    format: 'es',
  },
})