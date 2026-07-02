import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react-swc';
import path from 'path';

const DEFAULT_PLATFORM_DISPLAY_NAME = '宇宙和平论坛';
const PLATFORM_DISPLAY_NAME_PLACEHOLDER = '__PLATFORM_DISPLAY_NAME__';

const escapeHtmlText = (value: string): string =>
  value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, '');
  const platformDisplayName = env.PLATFORM_DISPLAY_NAME?.trim() || DEFAULT_PLATFORM_DISPLAY_NAME;

  return {
    envPrefix: ['VITE_', 'PLATFORM_'],
    plugins: [
      react(),
      {
        name: 'platform-html-title',
        transformIndexHtml(html) {
          return html.replace(
            PLATFORM_DISPLAY_NAME_PLACEHOLDER,
            escapeHtmlText(platformDisplayName)
          );
        },
      },
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      open: false,
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
        '/uploads': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
        '/downloads': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
    build: {
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom', 'react-router-dom'],
            ui: ['@radix-ui/react-dialog', '@radix-ui/react-dropdown-menu'],
            query: ['@tanstack/react-query'],
          },
        },
      },
    },
  };
});
