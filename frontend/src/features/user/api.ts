/**
 * 用户模块API
 * 处理用户相关请求
 */

import { apiClient } from '@/shared/api/client';
import type { UserProfile, UpdateUserData, CompleteProfileData } from './types';

/**
 * 用户API
 */
export const userApi = {
  /**
   * 获取用户列表
   * GET /api/v1/users/
   *
   * @param params - 查询参数
   * @returns 用户列表
   */
  getUsers: (params: { skip?: number; limit?: number } = {}) =>
    apiClient.get<UserProfile[]>('/users/', { params }),

  /**
   * 获取用户详情
   * GET /api/v1/users/{user_id}
   *
   * @param userId - 用户ID
   * @returns 用户详情
   */
  getUser: (userId: number) =>
    apiClient.get<UserProfile>(`/users/${userId}`),

  /**
   * 通过用户名获取用户
   * GET /api/v1/users/username/{username}
   *
   * @param username - 用户名
   * @returns 用户详情
   */
  getUserByUsername: (username: string) =>
    apiClient.get<UserProfile>(`/users/username/${username}`),

  /**
   * 更新用户信息
   * PUT /api/v1/users/{user_id}
   *
   * @param userId - 用户ID
   * @param data - 更新数据
   * @returns 更新后的用户信息
   */
  updateUser: (userId: number, data: UpdateUserData) =>
    apiClient.put<UserProfile>(`/users/${userId}`, data),

  /**
   * 完善用户资料（用于注册后设置用户名、签名等）
   * PUT /api/v1/users/{user_id}/complete-profile
   *
   * @param userId - 用户ID
   * @param data - 完善资料数据
   * @returns 更新后的用户信息
   */
  completeProfile: (userId: number, data: CompleteProfileData) =>
    apiClient.put<UserProfile>(`/users/${userId}/complete-profile`, data),

  /**
   * 上传用户头像
   * POST /api/v1/users/avatar
   *
   * @param file - 头像文件
   * @returns 更新后的用户信息
   */
  uploadAvatar: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post<UserProfile>('/users/avatar', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
  },

  /**
   * 删除用户头像
   * DELETE /api/v1/users/avatar
   *
   * @returns 更新后的用户信息
   */
  deleteAvatar: () =>
    apiClient.delete<UserProfile>('/users/avatar'),

  /**
   * 删除用户
   * DELETE /api/v1/users/{user_id}
   *
   * @param userId - 用户ID
   */
  deleteUser: (userId: number) =>
    apiClient.delete<void>(`/users/${userId}`),
};
