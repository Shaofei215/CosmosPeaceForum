/**
 * 信息流模块类型定义
 */

import type { Post } from '@/features/post/types';

export type FeedType = 'recommended' | 'latest' | 'following';

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
  /** 当前用户是否关注作者 */
  author_is_following?: boolean;
  /** 作者是否关注当前用户 */
  author_is_followed_by?: boolean;
  /** 当前用户与作者是否互相关注 */
  author_is_mutual?: boolean;
  /** 当前用户是否已点赞 */
  is_liked: boolean;
  /** 当前用户是否已点踩 */
  is_disliked: boolean;
  /** 当前用户是否已经投币。 */
  is_coined: boolean;
  /** 推荐热度分数 */
  heat_score?: number;
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
  /** 信息流类型 */
  feed_type?: FeedType;
  /** 推荐流 Top-N 重排种子 */
  seed?: string;
}
