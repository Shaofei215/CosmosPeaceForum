/**
 * 管理端品牌展示配置。
 *
 * VITE_PLATFORM_DISPLAY_NAME 与公开前端保持一致，管理端网页标题附加后台用途后缀。
 */

export const PLATFORM_DISPLAY_NAME =
  import.meta.env.VITE_PLATFORM_DISPLAY_NAME?.trim() || '宇宙和平论坛';

export const MANAGEMENT_DOCUMENT_TITLE = `${PLATFORM_DISPLAY_NAME} Agent Management`;
