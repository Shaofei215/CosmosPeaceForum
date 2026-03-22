/**
 * 点赞模块API
 */

import { apiClient } from '@/shared/api/client';
import type { LikeResponse, LikeStatusResponse } from './types';

/**
 * 点赞API
 */
export const likeApi = {
  /**
   * 点赞/取消点赞帖子
   * POST /api/v1/posts/{post_id}/like
   */
  toggleLike: (postId: number) =>
    apiClient.post<LikeResponse>(`/posts/${postId}/like`),

  /**
   * 获取点赞状态
   * GET /api/v1/posts/{post_id}/like-status
   */
  getLikeStatus: (postId: number) =>
    apiClient.get<LikeStatusResponse>(`/posts/${postId}/like-status`),
};
