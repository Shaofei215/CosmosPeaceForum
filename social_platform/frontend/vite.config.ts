import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react-swc';
import { existsSync } from 'node:fs';
import path from 'path';

const DEFAULT_PLATFORM_DISPLAY_NAME = '宇宙和平论坛';
const DEFAULT_API_V1_PREFIX = '/api/v1';
const PLATFORM_DISPLAY_NAME_PLACEHOLDER = '__PLATFORM_DISPLAY_NAME__';
const API_V1_PREFIX_PLACEHOLDER = '__API_V1_PREFIX__';
const PLATFORM_LOGO_PATH_PLACEHOLDER = '__PLATFORM_LOGO_PATH__';
const PLATFORM_LOGO_MIME_PLACEHOLDER = '__PLATFORM_LOGO_MIME__';
const PLATFORM_DARK_LOGO_PATH_PLACEHOLDER = '__PLATFORM_DARK_LOGO_PATH__';
const PLATFORM_DARK_LOGO_MIME_PLACEHOLDER = '__PLATFORM_DARK_LOGO_MIME__';
const BRAND_IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp', 'gif'] as const;

/**
 * 从 public 目录按品牌格式优先级选择构建时使用的图片。
 *
 * @param name 不含扩展名的品牌文件名。
 * @param fallback 全部格式均缺失时使用的备用图片。
 * @returns 图片的公开路径与 MIME 类型；无备用图片时返回 PNG 兼容路径。
 */
const resolvePublicBrandImage = (
  name: string,
  fallback?: { path: string; mime: string }
): { path: string; mime: string } => {
  const extension = BRAND_IMAGE_EXTENSIONS.find(candidate =>
    existsSync(path.resolve(__dirname, 'public', `${name}.${candidate}`))
  );
  if (extension === undefined && fallback !== undefined) return fallback;

  const resolvedExtension = extension ?? 'png';
  const mimeExtension = resolvedExtension === 'jpg' ? 'jpeg' : resolvedExtension;

  return { path: `/${name}.${resolvedExtension}`, mime: `image/${mimeExtension}` };
};

const escapeHtml = (value: string): string =>
  value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#x27;');

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, path.resolve(__dirname, '..'), '');
  const platformDisplayName = env.PLATFORM_DISPLAY_NAME?.trim() || DEFAULT_PLATFORM_DISPLAY_NAME;
  const apiV1Prefix = env.API_V1_PREFIX?.trim() || DEFAULT_API_V1_PREFIX;
  const platformLogo = resolvePublicBrandImage('icon');
  const platformDarkLogo = resolvePublicBrandImage('icon_dark', platformLogo);

  return {
    plugins: [
      react(),
      {
        name: 'platform-html-config',
        transformIndexHtml(html) {
          const brandedHtml = html
            .replaceAll(PLATFORM_LOGO_PATH_PLACEHOLDER, platformLogo.path)
            .replaceAll(PLATFORM_LOGO_MIME_PLACEHOLDER, platformLogo.mime)
            .replaceAll(PLATFORM_DARK_LOGO_PATH_PLACEHOLDER, platformDarkLogo.path)
            .replaceAll(PLATFORM_DARK_LOGO_MIME_PLACEHOLDER, platformDarkLogo.mime);

          if (command === 'serve') {
            return brandedHtml
              .replaceAll(PLATFORM_DISPLAY_NAME_PLACEHOLDER, escapeHtml(platformDisplayName))
              .replaceAll(API_V1_PREFIX_PLACEHOLDER, escapeHtml(apiV1Prefix));
          }

          return brandedHtml;
        },
      },
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      hmr: process.env.VITEST ? false : undefined,
      ws: process.env.VITEST ? false : undefined,
      host: '0.0.0.0',
      port: 5173,
      open: false,
      proxy: {
        [apiV1Prefix]: {
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
