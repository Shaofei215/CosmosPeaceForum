import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react-swc';
import { existsSync } from 'node:fs';
import path from 'path';

const DEFAULT_PLATFORM_DISPLAY_NAME = '宇宙和平论坛';
const PLATFORM_DISPLAY_NAME_PLACEHOLDER = '__PLATFORM_DISPLAY_NAME__';
const PLATFORM_LOGO_PATH_PLACEHOLDER = '__PLATFORM_LOGO_PATH__';
const PLATFORM_LOGO_MIME_PLACEHOLDER = '__PLATFORM_LOGO_MIME__';
const BRAND_IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp', 'gif'] as const;

/**
 * 从 public 目录按品牌格式优先级选择构建时使用的图片。
 *
 * @param name 不含扩展名的品牌文件名。
 * @returns 图片的公开路径与 MIME 类型；全部缺失时返回 PNG 兼容路径。
 */
const resolvePublicBrandImage = (name: string): { path: string; mime: string } => {
  const extension =
    BRAND_IMAGE_EXTENSIONS.find((candidate) =>
      existsSync(path.resolve(__dirname, 'public', `${name}.${candidate}`)),
    ) ?? 'png';
  const mimeExtension = extension === 'jpg' ? 'jpeg' : extension;

  return { path: `/${name}.${extension}`, mime: `image/${mimeExtension}` };
};

const escapeHtmlText = (value: string): string =>
  value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, '');
  const platformDisplayName =
    env.PLATFORM_DISPLAY_NAME?.trim() || DEFAULT_PLATFORM_DISPLAY_NAME;
  const platformLogo = resolvePublicBrandImage('logo');

  return {
    envPrefix: ['VITE_', 'PLATFORM_'],
    plugins: [
      react(),
      {
        name: 'management-html-title',
        transformIndexHtml(html) {
          return html.replace(
            PLATFORM_DISPLAY_NAME_PLACEHOLDER,
            escapeHtmlText(platformDisplayName),
          )
            .replace(PLATFORM_LOGO_PATH_PLACEHOLDER, platformLogo.path)
            .replace(PLATFORM_LOGO_MIME_PLACEHOLDER, platformLogo.mime);
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
      port: 5174,
      open: false,
      proxy: {
        '/api': {
          target: 'http://localhost:8001',
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
