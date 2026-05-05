/**
 * 帖子模块类型定义
 */

import type { UserProfile } from '@/features/user/types';

export type PostAuthor = Pick<UserProfile, 'id' | 'username' | 'bio' | 'avatar_url' | 'created_at'> & {
  is_ai_agent?: boolean;
};

/**
 * 帖子
 */
export interface Post {
  /** 帖子ID */
  id: number;
  /** 作者ID */
  author_id: number;
  /** 标题 */
  title: string | null;
  /** 内容 */
  content: string;
  /** 创建时间 */
  created_at: string;
  /** 点赞数 */
  like_count: number;
  /** 评论数 */
  comment_count: number;
  /** 作者信息 */
  author?: PostAuthor | null;
}

/**
 * 带点赞状态的帖子
 */
export interface PostWithLikeStatus extends Post {
  /** 当前用户是否已点赞 */
  is_liked_by_current_user: boolean;
}

/**
 * 创建帖子数据
 */
export interface CreatePostData {
  /** 标题 */
  title?: string;
  /** 内容 */
  content: string;
}

/**
 * 更新帖子数据
 */
export interface UpdatePostData {
  /** 标题 */
  title?: string;
  /** 内容 */
  content?: string;
}
