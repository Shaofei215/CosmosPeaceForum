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
  /** 转发数 */
  repost_count: number;
  /** 作者信息 */
  author?: PostAuthor | null;
  repost_source_type?: 'post' | 'comment' | null;
  repost_source_id?: number | null;
  repost_root_post_id?: number | null;
  repost_chain?: string | null;
  repost_chain_authors?: RepostChainAuthor[];
  repost_origin?: RepostOriginPost | null;
  repost_origin_missing?: boolean;
}

export interface RepostChainAuthor {
  user_id: number;
  username: string;
}

export interface RepostOriginPost {
  id: number;
  author_id: number;
  author?: PostAuthor | null;
  title: string | null;
  content: string;
  created_at: string;
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

export interface RepostData {
  content?: string;
  source_type: 'post' | 'comment';
  source_id: number;
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
