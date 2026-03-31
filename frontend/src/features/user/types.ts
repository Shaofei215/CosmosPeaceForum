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
  /** 关注数量 */
  following_count?: number;
  /** 粉丝数量 */
  followers_count?: number;
}

/**
 * 更新用户数据
 */
export interface UpdateUserData {
  /** 用户名 */
  username?: string;
  /** 个人简介 */
  bio?: string;
  /** 头像URL */
  avatar_url?: string;
}

/**
 * 完善用户资料数据
 */
export interface CompleteProfileData {
  /** 用户名（必填） */
  username: string;
  /** 个人简介（可选） */
  bio?: string;
  /** 头像URL（可选） */
  avatar_url?: string;
}
