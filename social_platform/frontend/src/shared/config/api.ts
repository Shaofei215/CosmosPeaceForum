/**
 * API配置
 * 定义API基础配置和常量
 */

/**
 * API基础配置
 */
export const API_CONFIG = {
  /** API基础URL */
  BASE_URL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  /** 请求超时时间（毫秒） */
  TIMEOUT: 10000,
  /** 重试次数 */
  RETRY_COUNT: 3,
} as const;

/**
 * 获取完整的头像URL
 * 如果已经是完整URL则直接返回
 * 如果是相对路径则拼接API基础URL的域名部分
 *
 * @param avatarUrl - 头像URL（相对或绝对）
 * @returns 完整的头像URL
 */
export function getFullAvatarUrl(avatarUrl: string | null | undefined): string | null {
  if (!avatarUrl) return null;

  if (
    avatarUrl.startsWith('http://') ||
    avatarUrl.startsWith('https://') ||
    avatarUrl.startsWith('blob:') ||
    avatarUrl.startsWith('data:')
  ) {
    return avatarUrl;
  }

  const baseUrl = API_CONFIG.BASE_URL.replace('/api/v1', '').replace(/\/$/, '');
  return `${baseUrl}/${avatarUrl.replace(/^\//, '')}`;
}

/**
 * HTTP状态码
 */
export const HTTP_STATUS = {
  OK: 200,
  CREATED: 201,
  NO_CONTENT: 204,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  SERVER_ERROR: 500,
} as const;

/**
 * 分页默认配置
 */
export const PAGINATION = {
  DEFAULT_PAGE: 1,
  DEFAULT_PAGE_SIZE: 20,
  MAX_PAGE_SIZE: 100,
} as const;

/**
 * 缓存时间配置（毫秒）
 */
export const CACHE_TIME = {
  /** 用户信息缓存时间 */
  USER: 5 * 60 * 1000, // 5分钟
  /** 帖子详情缓存时间 */
  POST: 5 * 60 * 1000, // 5分钟
  /** 信息流缓存时间 */
  FEED: 2 * 60 * 1000, // 2分钟
  /** 评论缓存时间 */
  COMMENT: 3 * 60 * 1000, // 3分钟
} as const;
