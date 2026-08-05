/**
 * 帖子模块类型定义
 */

import type { UserProfile } from '@/features/user/types';
import type { TopicMention } from '@/features/topic/types';

export type PostAuthor = Pick<UserProfile, 'id' | 'username' | 'bio' | 'avatar_url' | 'created_at'>;

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
  type: 'post' | 'article';
  /** 内容 */
  content: string;
  /** 创建时间 */
  created_at: string;
  /** 是否由 Agent 通道创建 */
  created_by_agent: boolean;
  /** 点赞数 */
  like_count: number;
  /** 点踩数 */
  dislike_count: number;
  /** 评论数 */
  comment_count: number;
  /** 转发数 */
  repost_count: number;
  /** 收到的硬币数。 */
  coin_count: number;
  /** 当前用户是否已经给该帖子投币。 */
  is_coined_by_current_user?: boolean;
  /** 作者信息 */
  author?: PostAuthor | null;
  repost_source_type?: 'post' | 'comment' | null;
  repost_source_id?: number | null;
  repost_root_post_id?: number | null;
  repost_chain?: string | null;
  repost_chain_authors?: RepostChainAuthor[];
  mention_users?: MentionUser[];
  topic_mentions?: TopicMention[];
  repost_origin?: RepostOriginPost | null;
  repost_origin_missing?: boolean;
  poll?: Poll | null;
}

export interface PollOption {
  id: number;
  text: string;
  position: number;
  vote_count: number;
  percentage: number;
}

export interface Poll {
  post_id: number;
  total_votes: number;
  has_voted: boolean;
  selected_option_id: number | null;
  options: PollOption[];
}

export interface MentionUser {
  user_id: number;
  username: string;
}

export interface RepostChainAuthor extends MentionUser {}

export interface RepostOriginPost {
  id: number;
  author_id: number;
  author?: PostAuthor | null;
  title: string | null;
  type: 'post' | 'article';
  content: string;
  created_at: string;
  created_by_agent: boolean;
}

/**
 * 带点赞状态的帖子
 */
export interface PostWithLikeStatus extends Post {
  /** 当前用户是否已点赞 */
  is_liked_by_current_user: boolean;
  /** 当前用户是否已点踩 */
  is_disliked_by_current_user: boolean;
}

/**
 * 创建帖子数据
 */
export interface CreatePostData {
  /** 标题 */
  title?: string;
  type?: 'post' | 'article';
  /** 内容 */
  content: string;
  /** 投票选项，仅右栏普通发帖入口使用 */
  poll_options?: string[];
}

export interface PollVoteData {
  option_id: number;
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
