import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Split the heavy vendor libraries into their own chunks so the main bundle stays
        // small and these cache independently across deploys (they change rarely).
        manualChunks: {
          'react-vendor': ['react', 'react-dom'],
          msal: ['@azure/msal-browser', '@azure/msal-react'],
          charts: ['recharts'],
          markdown: ['react-markdown'],
          motion: ['framer-motion'],
        },
      },
    },
  },
})
