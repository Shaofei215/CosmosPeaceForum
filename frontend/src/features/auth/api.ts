/**
 * 认证模块API
 * 处理登录、注册等认证相关请求
 */

import { apiClient } from '@/shared/api/client';
import type { LoginCredentials, RegisterCredentials, AuthResponse, User } from './types';

/**
 * 认证API
 */
export const authApi = {
  /**
   * 用户登录
   * POST /api/v1/auth/login
   *
   * @param credentials - 登录凭证
   * @returns 认证响应，包含访问令牌
   */
  login: (credentials: LoginCredentials) =>
    apiClient.post<AuthResponse>('/auth/login', credentials),

  /**
   * 用户注册
   * POST /api/v1/auth/register
   *
   * @param credentials - 注册凭证
   * @returns 新创建的用户信息
   */
  register: (credentials: RegisterCredentials) =>
    apiClient.post<User>('/auth/register', credentials),

  /**
   * 获取当前用户信息
   * GET /api/v1/auth/me
   *
   * @returns 当前登录用户信息
   */
  getCurrentUser: () =>
    apiClient.get<User>('/auth/me'),
};
