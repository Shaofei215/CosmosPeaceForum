/**
 * 管理端品牌展示配置。
 *
 * 管理后端从 agents/.env 读取 PLATFORM_DISPLAY_NAME，并将其注入页面元数据。
 */

const DEFAULT_PLATFORM_DISPLAY_NAME = '宇宙和平论坛';
const PLATFORM_DISPLAY_NAME_PLACEHOLDER = '__PLATFORM_DISPLAY_NAME__';

const injectedPlatformDisplayName = document
  .querySelector<HTMLMetaElement>('meta[name="platform-display-name"]')
  ?.content.trim();

export const PLATFORM_DISPLAY_NAME =
  injectedPlatformDisplayName &&
  injectedPlatformDisplayName !== PLATFORM_DISPLAY_NAME_PLACEHOLDER
    ? injectedPlatformDisplayName
    : DEFAULT_PLATFORM_DISPLAY_NAME;
