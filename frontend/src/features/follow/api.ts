/**
 * 关注模块API
 */

import { apiClient } from '@/shared/api/client';
import type {
  FollowToggleResponse,
  FollowStatusResponse,
  FollowListResponse,
  FollowerListResponse,
} from './types';

export const followApi = {
  toggleFollow: (userId: number) =>
    apiClient.post<FollowToggleResponse>(`/users/${userId}/follow`),

  getFollowStatus: (userId: number) =>
    apiClient.get<FollowStatusResponse>(`/users/${userId}/follow-status`),

  getFollowing: (
    userId: number,
    params?: { page?: number; page_size?: number }
  ) =>
    apiClient.get<FollowListResponse>(`/users/${userId}/following`, {
      params,
    }),

  getFollowers: (
    userId: number,
    params?: { page?: number; page_size?: number }
  ) =>
    apiClient.get<FollowerListResponse>(`/users/${userId}/followers`, {
      params,
    }),

  getMyFollowing: (params?: { page?: number; page_size?: number }) =>
    apiClient.get<FollowListResponse>('/users/me/following', { params }),

  getMyFollowers: (params?: { page?: number; page_size?: number }) =>
    apiClient.get<FollowerListResponse>('/users/me/followers', { params }),
};
