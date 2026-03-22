/**
 * 用户模块类型定义
 */

/**
 * 用户资料
 */
export interface UserProfile {
  /** 用户ID */
  id: number;
  /** 用户名 */
  username: string;
  /** 个人简介 */
  bio: string | null;
  /** 头像URL */
  avatar_url: string | null;
  /** 创建时间 */
  created_at: string;
}

/**
 * 更新用户数据
 */
export interface UpdateUserData {
  /** 个人简介 */
  bio?: string;
  /** 头像URL */
  avatar_url?: string;
}
