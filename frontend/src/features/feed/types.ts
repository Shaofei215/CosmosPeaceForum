/**
 * 信息流模块类型定义
 */

import type { Post } from '@/features/post/types';

/**
 * 信息流帖子项
 */
export interface PostFeedItem extends Post {
  /** 作者名称 */
  author_name: string;
  /** 作者头像 */
  author_avatar: string | null;
  /** 作者签名 */
  author_bio: string | null;
  /** 当前用户是否已点赞 */
  is_liked: boolean;
}

/**
 * 信息流查询参数
 */
export interface FeedParams {
  /** 页码 */
  page?: number;
  /** 每页数量 */
  page_size?: number;
  /** 当前用户ID */
  current_user_id?: number;
}
