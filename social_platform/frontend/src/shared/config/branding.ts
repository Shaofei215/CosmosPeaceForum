/**
 * 平台品牌展示配置。
 *
 * 前端展示名通过 Vite 注入的 PLATFORM_DISPLAY_NAME 配置。
 */

export const PLATFORM_DISPLAY_NAME =
  import.meta.env.PLATFORM_DISPLAY_NAME?.trim() || '宇宙和平论坛';
