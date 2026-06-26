/**
 * Management 管理员认证 API 封装。
 *
 * logout 会撤销当前服务端 admin session，refresh 由共享 apiClient 自动处理。
 */

import { apiClient } from '@/shared/api/client';
import type {
  AdminProfileUpdateRequest,
  AdminUser,
  LoginRequest,
  LoginResponse,
} from '@/shared/types/api';

export const authApi = {
  login: (credentials: LoginRequest) =>
    apiClient.post<LoginResponse>('/auth/login', credentials),

  getCurrentAdmin: () =>
    apiClient.get<AdminUser>('/auth/me'),

  updateProfile: (request: AdminProfileUpdateRequest) =>
    apiClient.put<AdminUser>('/auth/profile', request),

  logout: () =>
    apiClient.post<{ message: string }>('/auth/logout'),
};
