/**
 * 平台品牌展示配置。
 *
 * 展示名由公开平台后端从 social_platform/.env 注入页面元数据。
 */

const injectedPlatformDisplayName = document
  .querySelector<HTMLMetaElement>('meta[name="platform-display-name"]')
  ?.content.trim();

export const PLATFORM_DISPLAY_NAME = injectedPlatformDisplayName || '宇宙和平论坛';
