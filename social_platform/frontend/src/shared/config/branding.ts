/**
 * 平台品牌展示配置。
 *
 * 前端展示名通过 Vite 注入的 VITE_PLATFORM_DISPLAY_NAME 配置，兼容 VITE_PROJECT_NAME。
 */

export const PLATFORM_DISPLAY_NAME =
  import.meta.env.VITE_PLATFORM_DISPLAY_NAME?.trim() ||
  import.meta.env.VITE_PROJECT_NAME?.trim() ||
  '宇宙和平论坛';
