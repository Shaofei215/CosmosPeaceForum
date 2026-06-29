/**
 * 评论模块类型定义
 */

import type { MentionUser } from '@/features/post/types';
import type { UserProfile } from '@/features/user/types';

export type CommentSort = 'default' | 'latest';

/**
 * 评论
 */
export interface Comment {
  /** 评论ID */
  id: number;
  /** 帖子ID */
  post_id: number;
  /** 评论者ID */
  owner_id: number;
  /** 语义回复目标ID（null表示一级评论） */
  parent_id: number | null;
  /** 所属一级评论ID（一级评论为null，回复为对应一级评论ID） */
  root_comment_id: number | null;
  /** 评论内容 */
  content: string;
  /** 点赞数 */
  like_count: number;
  /** 回复数 */
  reply_count: number;
  /** 推荐热度分数 */
  heat_score?: number;
  /** 创建时间 */
  created_at: string;
  /** 是否由 Agent 通道创建 */
  created_by_agent: boolean;
  /** 当前用户是否已点赞 */
  is_liked: boolean;
  /** 评论者信息 */
  owner: UserProfile;
  /** 正文中可跳转的提及用户 */
  mention_users?: MentionUser[];
  /** 被回复的评论（仅用于展示“回复 @某人”） */
  parent?: {
    id: number;
    owner_id: number;
    owner?: UserProfile | null;
  } | null;
  /** 兼容字段；回复通过 replies 接口分页加载 */
  children: Comment[];
}

/**
 * 创建评论数据
 */
export interface CreateCommentData {
  /** 评论内容 */
  content: string;
  /** 父评论ID（回复时填写） */
  parent_id?: number;
  /** 是否评论并转发 */
  repost?: boolean;
}

/**
 * 评论列表响应
 */
export interface CommentListResponse {
  /** 评论列表 */
  items: Comment[];
  /** 总数 */
  total: number;
  /** 跳过数量 */
  skip: number;
  /** 限制数量 */
  limit: number;
}

/**
 * 评论点赞响应
 */
export interface CommentLikeResponse {
  /** 是否已点赞 */
  is_liked: boolean;
  /** 点赞数 */
  like_count: number;
  /** 当前点赞关系是否由 Agent 通道创建 */
  created_by_agent?: boolean;
}
