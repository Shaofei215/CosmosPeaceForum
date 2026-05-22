/**
 * 信息流模块API
 */

import { apiClient } from '@/shared/api/client';
import type { PaginatedResponse } from '@/shared/types/api';
import type { PostFeedItem, FeedParams } from './types';

/**
 * 信息流API
 */
export const feedApi = {
  /**
   * 获取全局信息流
   * GET /api/v1/feeds/feed/all
   */
  getGlobalFeed: (params: FeedParams = {}) =>
    apiClient.get<PaginatedResponse<PostFeedItem>>('/feeds/feed/all', { params }),

  /**
   * 获取用户帖子流
   * GET /api/v1/feeds/feed/user/{user_id}
   */
  getUserFeed: (userId: number, params: FeedParams = {}) =>
    apiClient.get<PaginatedResponse<PostFeedItem>>(`/feeds/feed/user/${userId}`, { params }),
};
