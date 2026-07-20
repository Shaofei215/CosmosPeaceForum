/**
 * 评论模块API
 */

import { apiClient } from '@/shared/api/client';
import { validateRequiredContent } from '@/shared/lib/content';
import { copywriting } from '@/shared/config/copywriting';
import type {
  Comment,
  CommentSort,
  CreateCommentData,
  CommentListResponse,
  CommentLikeResponse,
} from './types';

/**
 * 评论API
 */
export const commentApi = {
  /**
   * 获取一级评论列表
   * GET /api/v1/posts/{post_id}/comments
   */
  getComments: (
    postId: number,
    params: {
      user_id?: number;
      skip?: number;
      limit?: number;
      sort?: CommentSort;
      seed?: string;
    } = {}
  ) => apiClient.get<CommentListResponse>(`/posts/${postId}/comments`, { params }),

  /**
   * 获取所属一级评论 thread 下的扁平回复
   * GET /api/v1/posts/{post_id}/comments/{comment_id}/replies
   */
  getCommentReplies: (
    postId: number,
    commentId: number,
    params: {
      skip?: number;
      limit?: number;
      sort?: CommentSort;
      seed?: string;
    } = {}
  ) =>
    apiClient.get<CommentListResponse>(`/posts/${postId}/comments/${commentId}/replies`, {
      params,
    }),

  /**
   * 获取评论详情
   * GET /api/v1/posts/{post_id}/comments/{comment_id}
   */
  getComment: (postId: number, commentId: number, userId?: number) =>
    apiClient.get<Comment>(`/posts/${postId}/comments/${commentId}`, {
      params: userId ? { user_id: userId } : undefined,
    }),

  /**
   * 创建评论
   * POST /api/v1/posts/{post_id}/comments
   */
  createComment: (postId: number, data: CreateCommentData) =>
    apiClient.post<Comment>(`/posts/${postId}/comments`, {
      ...data,
      content: validateRequiredContent(data.content, copywriting('content.comment', '评论')),
    }),

  /**
   * 删除评论
   * DELETE /api/v1/posts/{post_id}/comments/{comment_id}
   */
  deleteComment: (postId: number, commentId: number) =>
    apiClient.delete<void>(`/posts/${postId}/comments/${commentId}`),

  /**
   * 点赞/取消点赞评论
   * POST /api/v1/posts/{post_id}/comments/{comment_id}/like
   */
  toggleCommentLike: (postId: number, commentId: number) =>
    apiClient.post<CommentLikeResponse>(`/posts/${postId}/comments/${commentId}/like`),

  /**
   * 获取评论点赞状态
   * GET /api/v1/posts/{post_id}/comments/{comment_id}/like-status
   */
  getCommentLikeStatus: (postId: number, commentId: number) =>
    apiClient.get<CommentLikeResponse>(`/posts/${postId}/comments/${commentId}/like-status`),
};
