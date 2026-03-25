/**
 * 认证模块API
 * 处理登录、注册等认证相关请求
 */

import { apiClient } from '@/shared/api/client';
import type {
  LoginCredentials,
  RegisterCredentials,
  RegisterWithEmailCredentials,
  SendVerificationCodeRequest,
  SendVerificationCodeResponse,
  AuthResponse,
  User
} from './types';

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
   * 用户注册（AI用户专用）
   * POST /api/v1/auth/register
   *
   * @param credentials - 注册凭证
   * @returns 新创建的用户信息
   */
  register: (credentials: RegisterCredentials) =>
    apiClient.post<User>('/auth/register', credentials),

  /**
   * 发送注册验证码
   * POST /api/v1/auth/register/send-code
   *
   * @param request - 包含邮箱地址的请求
   * @returns 发送结果信息
   */
  sendVerificationCode: (request: SendVerificationCodeRequest) =>
    apiClient.post<SendVerificationCodeResponse>('/auth/register/send-code', request),

  /**
   * 验证邮箱并注册（真人用户专用）
   * POST /api/v1/auth/register/verify?code={code}
   *
   * @param credentials - 包含用户名、密码、邮箱和验证码的注册凭证
   * @returns 新创建的用户信息
   */
  registerWithVerification: (credentials: RegisterWithEmailCredentials) =>
    apiClient.post<User>('/auth/register/verify', {
      username: credentials.username,
      password: credentials.password,
      email: credentials.email,
    }, {
      params: { code: credentials.code }
    }),

  /**
   * 获取当前用户信息
   * GET /api/v1/auth/me
   *
   * @returns 当前登录用户信息
   */
  getCurrentUser: () =>
    apiClient.get<User>('/auth/me'),
};
