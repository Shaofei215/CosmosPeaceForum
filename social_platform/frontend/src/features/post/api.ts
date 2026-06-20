/**
 * 帖子模块API
 */

import { apiClient } from '@/shared/api/client';
import type {
  Poll,
  PollVoteData,
  Post,
  PostWithLikeStatus,
  CreatePostData,
  UpdatePostData,
  RepostData,
} from './types';

/**
 * 帖子API
 */
export const postApi = {
  /**
   * 获取帖子列表
   * GET /api/v1/posts/
   */
  getPosts: (params: { skip?: number; limit?: number } = {}) =>
    apiClient.get<Post[]>('/posts/', { params }),

  /**
   * 获取帖子详情
   * GET /api/v1/posts/{post_id}
   */
  getPost: (postId: number, currentUserId?: number) =>
    apiClient.get<PostWithLikeStatus>(`/posts/${postId}`, {
      params: currentUserId ? { user_id: currentUserId } : undefined,
    }),

  /**
   * 创建帖子
   * POST /api/v1/posts/
   */
  createPost: (data: CreatePostData) => apiClient.post<Post>('/posts/', data),

  votePoll: (postId: number, data: PollVoteData) =>
    apiClient.post<Poll>(`/posts/${postId}/poll/vote`, data),

  repost: (data: RepostData) => apiClient.post<Post>('/posts/repost', data),

  /**
   * 更新帖子
   * PUT /api/v1/posts/{post_id}
   */
  updatePost: (postId: number, data: UpdatePostData) =>
    apiClient.put<Post>(`/posts/${postId}`, data),

  /**
   * 删除帖子
   * DELETE /api/v1/posts/{post_id}
   */
  deletePost: (postId: number) => apiClient.delete<void>(`/posts/${postId}`),

  /**
   * 获取用户的帖子
   * GET /api/v1/posts/user/{user_id}
   */
  getUserPosts: (userId: number, params: { skip?: number; limit?: number } = {}) =>
    apiClient.get<Post[]>(`/posts/user/${userId}`, { params }),
};
