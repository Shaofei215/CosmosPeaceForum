/**
 * 评论模块类型定义
 */

import type { UserProfile } from '@/features/user/types';

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
  /** 父评论ID（null表示一级评论） */
  parent_id: number | null;
  /** 评论内容 */
  content: string;
  /** 点赞数 */
  like_count: number;
  /** 回复数 */
  reply_count: number;
  /** 创建时间 */
  created_at: string;
  /** 当前用户是否已点赞 */
  is_liked: boolean;
  /** 评论者信息 */
  owner: UserProfile;
  /** 子评论（回复） */
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
}
